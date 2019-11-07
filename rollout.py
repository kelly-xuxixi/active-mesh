#!/usr/bin/env python

from utils.logger import log_string
import time
from active_mvnet_tf import MVInputs, SingleInput, SingleInputFactory
import numpy as np
from replay_memory import trajectData

np.random.seed(1024)

# Used to add a new traj into replay memory
class Rollout(object):
    def __init__(self, agent, env, memory, FLAGS):
        self.agent = agent
        self.env = env
        self.mem = memory
        self.input_factory = SingleInputFactory(memory)
        self.FLAGS = FLAGS

    def single_input_for_state(self, state):
        return self.input_factory.make(
            azimuth=np.array(state[0]),
            elevation=np.array(state[1]),
            model_id=self.env.current_model
        )

    def go(self, i_idx, verbose=True, add_to_mem=True, mode='active', is_train=True):
        ''' does 1 rollout, returns mvnet_input'''

        state, model_id = self.env.reset(is_train, i_idx)
        actions = []
        mvnet_input = MVInputs(self.FLAGS, batch_size=1)

        mvnet_input.put(self.single_input_for_state(state), episode_idx=0)

        for e_idx in range(1, self.FLAGS.max_episode_length):

            tic = time.time()
            if mode == 'active':
                # if np.random.uniform(0, 1) < self.FLAGS.epsilon:
                #    probs = [1.0/8]*8
                #    agent_action = np.random.choice(self.env.action_space_n, p=probs)
                # else:
                agent_action = self.agent.select_action(mvnet_input, e_idx - 1, is_training=is_train)
            elif mode == 'random':
                probs = [1.0 / 8] * 8
                agent_action = np.random.choice(self.env.action_space_n, p=probs)
            elif mode == 'nolimit':
                agent_action = 0
            elif mode == 'oneway':
                if len(actions) == 0:
                    probs = [1.0 / 8] * 8
                    agent_action = np.random.choice(self.env.action_space_n, p=probs)
                    agent_action = np.random.choice([0, 1, 4, 7])
                else:
                    agent_action = actions[0]

            actions.append(agent_action)
            if mode is not 'nolimit':
                state, next_state, done, model_id = self.env.step(actions[-1])
            else:
                state, next_state, done, model_id = self.env.step(actions[-1], nolimit=True)

            mvnet_input.put(self.single_input_for_state(next_state), episode_idx=e_idx)

            if verbose:
                log_string('Iter: {}, e_idx: {}, azim: {}, elev: {}, model_id: {}, time: {}s'.format(
                    i_idx, e_idx, next_state[0], next_state[1], model_id, time.time() - tic
                ))

            if done:
                traj_state = state
                traj_state[0] += [next_state[0]]
                traj_state[1] += [next_state[1]]

                if add_to_mem:
                    temp_traj = trajectData(traj_state, actions, model_id)
                    self.mem.append(temp_traj)

                self.last_trajectory = traj_state
                break

        return mvnet_input, actions
