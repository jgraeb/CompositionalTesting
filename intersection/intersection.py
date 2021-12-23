#############################################################################
#                                                                           #
# Basic class for grid world intersection traffic simulation                #
# Josefine Graebener, Apurva Badithela                                      #
# Caltech, November 2021                                                       #
#                                                                           #
#############################################################################
from random import choice
import numpy as np
import sys
sys.path.append('..') # enable importing modules from an upper directory
from components.agent import Agent
from components.map import Map
from components.pedestrian import Pedestrian
from helper import *
import _pickle as pickle
import os
from copy import deepcopy
from ipdb import set_trace as st
from collections import OrderedDict as od
# from intersection.test_parameters import INTERSECTIONFILE

MAX_TIMESTEP = 30

def synthesize_filter():
    # TODO
    pass

def get_orientation(symb):
    """
    Read the layout of the intersection into the map.
    """
    if symb in ['←','⇠']:
        orientation = 'w'
    elif symb in ['→','⇢']:
        orientation = 'e'
    elif symb in ['↓','⇣']:
        orientation = 's'
    elif symb in ['↑','⇡']:
        orientation = 'n'
    elif symb == '+':
        orientation = None
    else:
        st()
    return orientation

class GridWorld:
    def __init__(self, initial_scene, intersectionfile, sys_agents=None, tester_agents=None, turn=None):
        self.map, self.crosswalk = self.create_intersection_from_file(intersectionfile)
        self.road_nodes, self.non_road_nodes = self.get_road_cells()
        self.transitions = self.get_edges()
        self.nodes = list(self.map.keys())
        self.initial_scene = initial_scene # dictionary of initial agent conditions
        if sys_agents is not None:
            self.sys_agents = sys_agents #
        else:
            self.sys_agents = [] # empty list of system agents (under test)
        self.tester_cars = []
        self.tester_peds = []
        if tester_agents is not None:
            pass
            # self.setup_testers()
        self.actions = {'stay': (0,0), 'n': (-1,0), 's': (1,0), 'w': (0,-1), 'e': (0,1)}
        self.goals = {'n':(0,4), 'e':(4,7), 's':(7,3), 'w':(3,0)}
        self.tester_actions = {'stay': (0,0),'s': (1,0)} # possible actions for testers
        self.ped_actions = {'forward': 1, 'back': -1, 'stay': 0}
        self.trace = []
        self.timestep = 0
        # Game conditions of the MCTS:
        if turn is not None:
            self.turn = turn
        else:
            self.turn = "tester"
        self.terminal = False # This is when ego arrives at its goal
        self.orientation_set = ['←','→','↓','↑','+','⇠','⇢','⇣','⇡']


    '''-----Basic gridworld setup functions-----'''
    def create_intersection_from_file(self,intersectionfile):
        map = od()
        f = open(intersectionfile, 'r')
        lines = f.readlines()
        len_y = len(lines)
        for i,line in enumerate(lines):
            for j,item in enumerate(line):
                if item != '\n':
                    map[i,j] = item
        # make dictionary that maps each crosswalk state to a grid cell
        # currenly manual -> TODO automatically from file
        crosswalk = dict()
        start_cw = 2
        end_cw = 6
        y = 2
        for i, num in enumerate(range(2*start_cw,2*(end_cw+1))):
            crosswalk.update({i: (int(np.floor(num/2)), y)})
        return map, crosswalk

    def get_road_cells(self):
        self.grid = od()
        non_road_nodes = []
        road_nodes = []
        for xy in self.map:
            if self.map[xy] == '*':
                non_road_nodes.append(xy)
            else:
                orientation = self.get_direction(xy)
                road_nodes.append(xy)
                self.grid[xy[0],xy[1]] = orientation
        return road_nodes, non_road_nodes

    def get_edges(self):
        transitions = dict()
        for cell in self.grid:
            dir = self.grid[cell]
            next_cells = []
            next_cells.append([cell]) # add self loop
            for item in dir:
                if item == 's':
                    nextcell = (cell[0]+1,cell[1])
                elif item == 'n':
                    nextcell = (cell[0]-1,cell[1])
                elif item=='w':
                    nextcell = (cell[0],cell[1]-1)
                elif item=='e':
                    nextcell = (cell[0],cell[1]+1)
                else:
                    nextcell = None
                if nextcell in self.map:
                    next_cells.append(nextcell)
                else:
                    next_cells.append((99,99)) # off the map
            transitions.update({cell : next_cells})
        return transitions

    def check_dir(self, loc, dir):
        if dir=='ns':
            k = 0
        elif dir=='ew':
            k = 1
        while True:
            dir1=loc[k]+1
            dir2=loc[k]-1
            if k == 1:
                check_loc1 = (loc[0],dir1)
                check_loc2 = (loc[0],dir2)
            else:
                check_loc1 = (dir1,loc[1])
                check_loc2 = (dir2, loc[1])
            if self.map[check_loc1] != '+':
                return get_orientation(self.map[check_loc1])
            if self.map[check_loc2] != '+':
                return get_orientation(self.map[check_loc2])

    def get_direction(self,xy):
        orientationset = get_orientation(self.map[xy])
        if not orientationset:
            ew = self.check_dir(xy,'ew')
            ns = self.check_dir(xy,'ns')
            orientationset = [str(ns),str(ew),str(ns)+str(ew)]
        return orientationset

    def setup_simple_test(self):
        # self.find_actions_for_cell()
        agent = (7,4) # initial position
        list_of_agents = [('Agent1',0,3,'s', 's'), ('Pedestrian', 2, 2, 0, 's')]
        self.sys_agents = [Agent(name='ego', x=agent[0],y=agent[1],v=0, goal='w', orientation = 'n')]
        for agent in list_of_agents:
            if agent[0] == 'Pedestrian':
                self.tester_peds.append(Pedestrian(name='Ped1', x=agent[1],y=agent[2],cwloc=agent[3], goal=agent[4]))
            else:
                self.tester_cars.append(Agent(name=agent[0], x=agent[1],y=agent[2],v=0, goal=agent[3], orientation = agent[4]))
        # self.tester_agents = [Agent(name=item[0], x=item[1],y=item[2],v=0, goal=item[3], orientation = item[4]) for item in list_of_agents]
        # agents = self.sys_agents + self.tester_agents
        self.print_intersection(self.timestep)
        # st()

    '''-----Basic gridworld simulation functions-----'''

    def strategy(self,agent):
        agent_actions = self.enabled_actions(agent)
        acts = []
        for val in agent_actions.keys():
            acts.append(val)

        if agent.goal in acts:
            return agent.goal
        action = np.random.choice(acts)
        return action

    def run_sim(self):
        trace = self.trace
        for i in range(1,25):
            self.timestep = i
            print('Step {}'.format(i))
            # testers take step
            for pedestrian in self.tester_peds:
                # currently pick a random enabled action
                action = choice([key for key in self.enabled_actions_pedestrian(pedestrian).keys()])
                self.pedestrian_take_step(pedestrian,action)
            for agent in self.tester_cars:
                action = choice([key for key in self.enabled_actions_car(agent).keys()])
                self.tester_take_step(agent,action)
            # agents = self.sys_agents + self.tester_agents
            self.print_intersection(self.timestep)
            # ego takes step
            for ego_agent in self.sys_agents:
                action = self.strategy(ego_agent)
                self.agent_take_step(ego_agent, action)
            # save the scene
            self.print_intersection(self.timestep)
            # check if we are done
            for agent in self.sys_agents:
                if self.is_terminal():
                    print('Goal reached')
                    # save the trace
                    print(self.trace)
                    save_trace(filepath, self.trace)
                    return
        save_trace(filepath, self.trace)

    def is_terminal(self):
        '''Returns if the state is terminal'''
        for agent in self.sys_agents:
            # st()
            goal = self.goals[agent.goal]
            if agent.y == goal[0] and agent.x == goal[1]:
                self.terminal = True
            else:
                if self.timestep >= MAX_TIMESTEP:
                    self.terminal = True
                else:
                    self.terminal = False
        return self.terminal

    def reward(self):
        '''Get reward for run'''
        if not self.terminal:
            raise RuntimeError("reward called on nonterminal gridworld")
        else:
            reward = self.timestep # TODO: add time left until red light here!
            # print('Returned REWARD')
            return reward

    def setup_world(self):
        '''Initializing the gridworld'''
        for i,agent in enumerate(self.initial_scene):
            if agent.name[0:3] =='sys':
                self.sys_agents.append(agent)
            else:
                self.tester_agents.append(agent)
        self.print_state()

    def get_actions(self,agent,agent_list):
        '''get all possible actions for an agent from its position'''
        agentpos = (agent[1],agent[2])
        enabled_actions = self.enabled_actions_from_loc(agentpos, agent_list)
        return enabled_actions

    def ego_take_input(self, action):
        '''Ego agent takes the step'''
        for agent in self.sys_agents:
            enabled_actions = self.enabled_actions(agent)
            if action in enabled_actions.keys():
                x,y = enabled_actions[action]
                agent.x = x
                agent.y = y
            elif 'move' in enabled_actions.keys():
                ran_act = choice(['move', 'stay'])
                x,y = enabled_actions[ran_act]
                agent.x = x
                agent.y = y
            else:
                x,y = enabled_actions['stay']
                agent.x = x
                agent.y = y

    def enabled_actions(self,agent):
        '''Find possible actions for agent'''
        enabled_actions = dict()
        x = agent.x
        y = agent.y
        if (x,y) not in self.grid: # if car left the intersection, it stays off
            acts = {'stay': (x,y)}
            return acts
        actions = self.grid[(x,y)] # all possible actions
        allowed_acts = []
        if agent.orientation in actions:
            allowed_acts.append(agent.orientation)
        if agent.goal in actions:
            allowed_acts.append(agent.goal)
        og = str(agent.orientation)+str(agent.goal)
        if og in actions:
            allowed_acts.append(og)
        go = str(agent.goal)+str(agent.orientation)
        if go in actions:
            allowed_acts.append(go)

        for action in allowed_acts:
            if action not in self.actions and not agent.turn:
                move_x,move_y = self.actions[agent.orientation]
            elif action not in self.actions and agent.turn:
                move_x,move_y = self.actions[agent.goal]
            else:
                move_x,move_y = self.actions[action]
            act_x = x + move_x
            act_y = y + move_y
            if (act_x,act_y) != (self.tester_cars[0].x, self.tester_cars[0].y) and (act_x,act_y) != (self.tester_peds[0].x, self.tester_peds[0].y):
                enabled_actions.update({action: (act_x,act_y)})
            enabled_actions.update({'stay': (x,y)}) # stay is always included
        return enabled_actions

    def enabled_actions_pedestrian(self,ped):
        '''Find possible actions for agent'''
        enabled_actions = dict()
        if type(ped) == list:
            cw_loc = ped[3]
        else:
            cw_loc = ped.cwloc
        gridpos = self.crosswalk[cw_loc]
        actions = self.ped_actions # all possible actions
        allowed_acts = []

        for action in actions:
            move_on_cw = self.ped_actions[action]
            new_cw_pos = cw_loc + move_on_cw
            if min(self.crosswalk.keys()) <= new_cw_pos <= max(self.crosswalk.keys()):
                if self.is_cell_free(self.crosswalk[new_cw_pos]):
                    enabled_actions.update({action: new_cw_pos})
            # enabled_actions.update({'stay': cw_loc}) # stay is always included
        return enabled_actions

    def enabled_actions_car(self,agent):
        '''Find possible actions for agent'''
        enabled_actions = dict()
        x = agent.x
        y = agent.y
        if (x,y) not in self.grid: # if car left the intersection, it stays off
            acts = {'stay': (x,y)}
            return acts
        actions = self.tester_actions # all possible actions
        allowed_acts = []
        for action in actions:
            move_x,move_y = self.tester_actions[action]
            act_x = x + move_x
            act_y = y + move_y
            if self.is_cell_free((act_x,act_y)):
                enabled_actions.update({action: (act_x,act_y)})
            enabled_actions.update({'stay': (x,y)}) # stay is always included
        return enabled_actions

    def find_transitions_from_cell(self):
        transitions_dict = {}
        child_nodes = []
        for key in self.grid:
            # st()
            child_nodes = []
            cell_actions = self.grid[key]
            for action in cell_actions:
                if action in self.actions:
                    new_x = key[0] + self.actions[action][0]
                    new_y = key[1] + self.actions[action][1]
                    child_nodes.append((new_x,new_y))
            child_nodes.append((key[0],key[1])) # stay is always included
            transitions_dict.update({key : child_nodes})
        return transitions_dict

    def match_actions_to_transitions(self):
        actions_dict = {}
        child_nodes = []
        for key in self.grid:
            child_nodes = []
            cell_actions = self.grid[key]
            for action in cell_actions:
                if action in self.actions:
                    new_x = key[0] + self.actions[action][0]
                    new_y = key[1] + self.actions[action][1]
                    child_nodes.append((new_x,new_y,action))
            child_nodes.append((key[0], key[1], 'stay')) # stay is always included
            actions_dict.update({key : child_nodes})
        return actions_dict

    def is_cell_free(self, cellxy, agent_list = None):
        '''check if the cell is free'''
        x,y = cellxy
        if not agent_list:
            agents = self.sys_agents + self.tester_cars
            for agent in agents:
                if agent.x == x and agent.y == y:
                    return False
        else:
            for pos in agent_list: # check all env agents
                if pos[1] == x and pos[2] == y:
                    return False
            for agent in self.sys_agents:
                if agent.x == x and agent.y == y:
                    return False
        return True

    def agent_take_step(self,agent,action):
        print('Agent chose {}'.format(action))
        '''Take the step for env, used for actually taking the actions during execution'''
        enabled_actions = self.enabled_actions(agent)
        if action in enabled_actions:
            x,y = enabled_actions[action]
            agent.x = x
            agent.y = y
            if action in self.actions and action != 'stay':
                agent.orientation = action
        else:
            x,y = enabled_actions['stay']
            agent.x = x
            agent.y = y

    def tester_take_step(self, agent, action):
        print('Agent {0} chose {1}'.format(agent.name, action))
        '''Take the step for env, used for actually taking the actions during execution'''
        enabled_actions = [key for key in self.enabled_actions(agent).keys()]
        if action in enabled_actions:
            move_x,move_y = self.tester_actions[action]
            agent.x = agent.x + move_x
            agent.y = agent.y + move_y
            if action in self.actions and action != 'stay':
                agent.orientation = action

    def pedestrian_take_step(self, ped, action):
        print('Pedestrian {0} choses {1}'.format(ped.name, action))
        '''Take the step for pedestrians, used for actually taking the actions during execution'''
        enabled_actions = [key for key in self.enabled_actions_pedestrian(ped).keys()]
        if action in enabled_actions:
            # st()
            delta_cw_loc = self.ped_actions[action]
            cw_loc = ped.cwloc + delta_cw_loc
            ped.x = self.crosswalk[cw_loc][0]
            ped.y = self.crosswalk[cw_loc][1]
            ped.cwloc = cw_loc
        else:
            # Pedestrian stayed in place
            print('Pedestrian stayed')

    def print_intersection(self, timestep):
        # save the scene
        self.trace = save_scene(self,self.trace)
        print('Timestep '+str(timestep))
        k_old = 0
        line = ""
        agent_positions = [(agent.x,agent.y) for agent in self.tester_cars]
        agent_positions.append((self.sys_agents[0].x,self.sys_agents[0].y))
        ped_positions = [(ped.x, ped.y) for ped in self.tester_peds]
        for item in self.map:
            k_new = item[0]
            if item in agent_positions:
                symb = 'o'
            elif item in ped_positions:
                symb = 'P'
            else:
                symb = self.map[item]
            if k_new == k_old:
                line += ' ' if symb == '*' else str(symb)
            else:
                print(line)
                k_old = item[0]
                line = ' ' if symb == '*' else str(symb)
        print(line)

    def set_traffic_light_color(self):
        # LIGHTCYCLE = []
        # 15 set as light cycle
        light = self.timestep % 15
        if  light < 10:
            light = 'g'
        elif 10 <= light <= 12:
            light = 'y'
        else:
            light = 'r'

    def print_state(self):
        # save the scene
        # self.trace = save_scene(self,self.trace)
        print('Timestep '+str(self.timestep))
        k_old = 0
        line = ""
        agent_positions = [(agent.x,agent.y) for agent in self.tester_cars]
        agent_positions.append((self.sys_agents[0].x,self.sys_agents[0].y))
        ped_positions = [(ped.x, ped.y) for ped in self.tester_peds]
        for item in self.map:
            k_new = item[0]
            if item in agent_positions:
                symb = 'o'
            elif item in ped_positions:
                symb = 'P'
            else:
                symb = self.map[item]
            if k_new == k_old:
                line += ' ' if symb == '*' else str(symb)
            else:
                print(line)
                k_old = item[0]
                line = ' ' if symb == '*' else str(symb)
        print(line)

    """ Basic mcts functions """
    def take_next_step(self, agent, action, agent_dict, sys_agent, check=False):
        '''Given a list of agent positions, update the chosen agent position after the step'''
        if agent[0] == 'Ped1':
            name = 'ped'
        else:
            name = 'car'
        # make this move
        if name == 'car':
            agentpos = (agent_dict[name][1],agent_dict[name][2])
        else:
            agentpos = (agent_dict[name][3])
        enabled_actions = self.enabled_actions_for_rollout(name, agentpos, agent_dict, sys_agent)
        # st()
        if name == 'car':
            agent_dict[name][1] = enabled_actions[action][0]
            agent_dict[name][2] = enabled_actions[action][1]
        else:
            try:
                agent_dict[name][3] = enabled_actions[action]
            except:
                st()
            agent_dict[name][1] = self.crosswalk[enabled_actions[action]][0]
            agent_dict[name][2] = self.crosswalk[enabled_actions[action]][1]
        return agent_dict

    def enabled_actions_for_rollout(self, name, agentpos, agent_dict, sys_agent):
        enabled_actions = dict()
        if name == 'car':
            actions = self.tester_actions
            allowed_acts = []
            for action in actions:
                move_xy = self.tester_actions[action]
                new_x = agentpos[0] + move_xy[0]
                new_y = agentpos[1] + move_xy[1]
                if (new_x, new_y) != sys_agent and (new_x, new_y) != self.crosswalk[agent_dict['ped'][3]]:
                    enabled_actions.update({action: (new_x, new_y)})
        elif name == 'ped':
            cw_loc = agentpos
            gridpos = self.crosswalk[cw_loc]
            actions = self.ped_actions # all possible actions
            allowed_acts = []
            for action in actions:
                move_on_cw = self.ped_actions[action]
                new_cw_pos = cw_loc + move_on_cw
                if min(self.crosswalk.keys()) <= new_cw_pos <= max(self.crosswalk.keys()):
                    if gridpos != sys_agent and gridpos != (agent_dict['car'][1],agent_dict['car'][2]):
                        enabled_actions.update({action: new_cw_pos})
                # enabled_actions.update({'stay': cw_loc}) # stay is always included
        return enabled_actions

    def find_children(self, debug = False):
        # st()
        # print('Finding all node children to world')
        # self.print_state()
        '''Find all children for a node'''
        if self.terminal:
            return set()
        if self.turn == "tester": # the testers take their turn
            #agent = 'ag_env'
            children = set()
            count = 1
            for gi in self.get_children_gridworlds(debug):
                gi.turn = "sys"
                gi.timestep = self.timestep + 1
                children.add(gi)
                # print(gi.turn + " can play ")
        else: # the system takes its turn
            for agent in self.sys_agents:
                agent_actions = self.enabled_actions(agent)
                if agent.x == 3:
                    if 'n' in agent_actions.keys():
                        agent_actions.pop('n')
                    if 'nw' in agent_actions.keys():
                        agent_actions.pop('nw')
                # self.print_state()
                # print('agent is at x {0}, y {1}'.format(agent.x,agent.y))
                # print('possible actions are: {}'.format(agent_actions.keys()))
                # actions = self.strategy(agent)
                children = set()
                count = 1
                for ai in agent_actions:
                    x,y = agent_actions[ai]
                    intersectionfile = os.getcwd()+'/intersection/intersectionfile.txt'
                    gi = GridWorld([], intersectionfile)
                    if ai == 'stay':
                        orientation = agent.orientation
                    else:
                        orientation = ai
                    sys_agents = [Agent(name=agent.name, x=x,y=y,v=agent.v, goal=agent.goal, orientation = orientation)]
                    gi.sys_agents = sys_agents
                    gi.tester_cars = self.tester_cars
                    gi.tester_peds = self.tester_peds
                    count = count+1
                    gi.timestep = self.timestep + 1
                    children.add(gi)
                    # print(gi.turn + " can play ")
        return children

    def find_random_child(self):
        # print('finding random child')
        debug = False
        '''Pick a random child node'''
        if self.terminal:
            return None

        children = self.find_children()
        if debug:
            # print_child_gridworlds(children)
            st()
        try:
            ran_child = choice(list(children))
        except:
            st()
            debug = True
            children = self.find_children(debug)
        if debug:
            print('Picked:')
            ran_child.print_state()
        return ran_child

    def get_children_gridworlds(self,debug=False):
        # print('Getting children gridworlds')
        if debug:
            st()
        # st()
        '''Find all children nodes from the current node for env action next'''
        # prep the agent data
        testers_original = dict()
        # st()
        sys_agent = (self.sys_agents[0].x, self.sys_agents[0].y)
        for agent in self.tester_cars:
            testers_original.update({'car': [agent.name, agent.x, agent.y, agent.v, agent.goal, agent.orientation]})
        for agent in self.tester_peds:
            testers_original.update({'ped': [agent.name, agent.x, agent.y, agent.cwloc, agent.goal]})
        # st()
        # list_of_agentlists = [agent_list_original]
        # do all combinations of actions that are possible and then check
        list_of_tester_agents = []
        # pick action for first agent
        ped = testers_original['ped']
        car = testers_original['car']
        # actions1 = self.get_actions(agent1,agent_list_original)
        actions1 = self.enabled_actions_pedestrian(ped)
        for action1 in actions1:
            testers_new = deepcopy(testers_original)
            # take the step
            # st()
            testers_new = self.take_next_step(ped, action1, testers_new, sys_agent)
            # actions2 = self.get_actions(agent2, agent_list_copy)
            # st()
            agentpos = (car[1],car[2])
            actions2 = self.enabled_actions_for_rollout('car', agentpos, testers_new, sys_agent)
            # st()
            for action2 in actions2:
                testers_new_2 = deepcopy(testers_new)
                check = True
                testers_new_2 = self.take_next_step(car, action2, testers_new_2, check, debug)
                if testers_new_2 is not None:
                    # print('A gridworld child was found')
                    # st()
                    list_of_tester_agents.append(testers_new_2)
        # list_of_agentlists = deepcopy(list_of_tester_agents)
        list_of_gridworlds = [make_gridworld(agent_dict, self.sys_agents) for agent_dict in list_of_tester_agents]
        # st()
        return list_of_gridworlds

def make_gridworld(agent_dict, sys_agents):
    '''Create a gridworld from a list of agents'''
    intersectionfile = os.getcwd()+'/intersection/intersectionfile.txt'
    gi = GridWorld([],intersectionfile)
    gi.sys_agents = sys_agents
    car_data = agent_dict['car']
    gi.tester_cars = [Agent(name=car_data[0], x=car_data[1],y=car_data[2],v=0, goal=car_data[3], orientation = car_data[4])]
    ped_data = agent_dict['ped']
    gi.tester_peds = [Pedestrian(name=ped_data[0], x=ped_data[1],y=ped_data[2],cwloc=ped_data[3], goal=ped_data[4])]
    return gi

def run_intersection_gridworld():
    print('Intersection Example')
    intersectionfile = 'intersectionfile.txt'
    gw = GridWorld([],intersectionfile)
    gw.setup_simple_test()
    gw.run_sim()

def make_state_dictionary_for_specification():
    """
    Function which returns list of next possible cells for each cell in the grid.

    return values:
    transitions_dict: Dictionary of states with list of child states
    actions_dict: Dictionary of states with list of child states and matching actions

    """
    print('Intersection Example')
    intersectionfile = 'intersectionfile.txt'
    gw = GridWorld([],intersectionfile)
    gw.setup_simple_test()
    transitions_dict = gw.find_transitions_from_cell()
    actions_dict = gw.match_actions_to_transitions()
    # print(transitions_dict)
    return transitions_dict, actions_dict



if __name__ == '__main__':
    output_dir = os.getcwd()+'/saved_traces/'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    filename = 'sim_trace.p'
    filepath = output_dir + filename

    # make_state_dictionary_for_specification()

    run_intersection_gridworld()