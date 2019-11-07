import os
import sys
import numpy as np
import scipy.misc as sm
import matplotlib.pyplot as plt
import random

np.random.seed(2048)

cat_name = {
    "02691156": "airplane",
    # "02828884",
    # "02933112",
    "03001627": "chair",
    # "03211117",
    # "03636649",
    # "03691459",
    # "04090263",
    # "04256520",
    # "04379243",
    # "04401088",
    # "04530566",
    "02958343": "car",
    "03797390": "mug",
    "0000": "combine",
    "1111": "1111",
    "2222": "double_mug",
    "3333": "mix4_all"
}

# azim_all = np.linspace(0, 360, 37)
# azim_all = azim_all[0:-1]
# azim_for_init = np.linspace(0, 360, 9)
# azim_for_init = np.asarray([0, 40, 90, 120, 180, 210, 270, 330])
# elev_all = np.linspace(10, 60, 6)
# elev_for_init = np.asarray([20, 40, 60])
azim_all = np.linspace(0, 360, 9)
azim_all = azim_all[0:-1]               # [0, 45, 90, 135, 180, 225, 270, 315]
azim_for_init = np.linspace(0, 360, 5)
azim_for_init = azim_for_init[0:-1]     # [0, 90, 180, 270]
elev_all = np.linspace(-30, 30, 5)      # [-30, -15, 0, 15, 30]
elev_for_init = np.asarray([-15, 0, 15])    # [-15, 0, 15]


class ShapeNetEnv():
    def __init__(self, FLAGS):
        self.FLAGS = FLAGS
        self.max_episode_length = FLAGS.max_episode_length

        self.category = FLAGS.category
        FLAGS.train_filename_prefix

        # Load train/val/test model name
        self.lists_dir = 'data/render_scripts/lists/{}_lists/'.format(self.category)
        with open(self.lists_dir + '{}_idx.txt'.format(FLAGS.train_filename_prefix), 'r') as f:
            # with open('data/render_scripts/lists/02958343_lists/train_idx.txt', 'r') as f:
            self.train_list = f.read().splitlines()
            # np.random.shuffle(self.train_list)

        with open(self.lists_dir + '{}_idx.txt'.format(FLAGS.val_filename_prefix), 'r') as f:
            self.val_list = f.read().splitlines()
            # np.random.shuffle(self.val_list)

        with open(self.lists_dir + '{}_idx.txt'.format(FLAGS.test_filename_prefix), 'r') as f:
            self.test_list = f.read().splitlines()
            np.random.shuffle(self.test_list)

        # TODO: Load Mesh data
        # 'data/data_cache/blender_renderings/02958343/res128_car/'
        self.data_dir = 'data/data_cache/blender_renderings/{}/res{}_{}/'.format(self.category,
                                                                                 FLAGS.resolution,
                                                                                 cat_name[self.category])

        self.trainval_list = self.train_list + self.val_list
        self.train_len = len(self.trainval_list)
        self.test_len = len(self.test_list)
        self.step_count = 0
        self.current_model = None
        self.current_azim = np.float32(0.0)
        self.current_elev = np.float32(30.0)
        self.prev_azims = []
        self.prev_elevs = []
        self.test_count = 0
        self.azim_for_init = azim_for_init
        self.elev_for_init = elev_for_init
        self.test_azims = np.random.choice(self.azim_for_init, size=(self.test_len, 1)) # Fix starting azim/elev for test
        self.test_elevs = np.random.choice(self.elev_for_init, size=(self.test_len, 1))
        self.action_space_n = 8
        self.azim_all = azim_all
        self.elev_all = elev_all

    # Random choose a model, and randomly set it's starting pos
    def reset(self, is_training, test_idx=0):
        self.step_count = 0
        self.prev_azims = []
        self.prev_elevs = []
        if is_training:     # random choose starting azim/elev
            rand_idx = np.random.randint(0, self.train_len)
            self.current_model = self.trainval_list[rand_idx]
            # self.current_azim = np.random.choice(azim_all)
            self.current_azim = np.random.choice(self.azim_for_init)
            # self.current_elev = np.random.choice(elev_all)
            self.current_elev = np.random.choice(self.elev_for_init)
        else:               # For test, has to make sure starting pos is same for the same index
            if self.FLAGS.debug_train:   # Whether is testing on training data
                t_idx = min(test_idx, self.train_len)
                self.current_model = self.trainval_list[t_idx]
            else:
                t_idx = min(test_idx % self.test_len, self.test_len - 1)  # = test_idx % self.test_len
                self.current_model = self.test_list[t_idx]

            if test_idx >= self.test_len:  # why add 80 in this case?
                self.current_azim = np.mod(self.test_azims[t_idx] + 80, 360)
                self.current_elev = self.test_elevs[t_idx]
            else:
                self.current_azim = np.mod(self.test_azims[t_idx], 360)
                self.current_elev = self.test_elevs[t_idx]

        # if self.FLAGS.debug_single:
        #     self.current_model = self.trainval_list[0]

        return [[self.current_azim], [self.current_elev]], self.current_model

    # Change current pos based on action
    def step(self, action, nolimit=False):

        self.prev_azims += [self.current_azim]
        self.prev_elevs += [self.current_elev]

        MAX_ELEV = np.float(60.0)
        MIN_ELEV = np.float(10.0)
        if self.FLAGS.category == '2222' or self.FLAGS.category == '3333':
            MIN_ELEV = np.float(20)
        DELTA = self.FLAGS.delta

        # chenxi
        DELTA_AZIM = 45
        DELTA_ELE = 15
        MAX_ELEV = np.float(30.0)
        MIN_ELEV = np.float(-30.0)

        if action == 0:
            self.current_azim = np.mod(self.current_azim + DELTA_AZIM, 360)
        elif action == 1:
            self.current_azim = np.mod(self.current_azim - DELTA_AZIM, 360)
        elif action == 2:
            self.current_elev = np.minimum(self.current_elev + DELTA_ELE, MAX_ELEV)
        elif action == 3:
            self.current_elev = np.maximum(self.current_elev - DELTA_ELE, MIN_ELEV)
        elif action == 4:
            self.current_azim = np.mod(self.current_azim + DELTA_AZIM, 360)
            self.current_elev = np.minimum(self.current_elev + DELTA_ELE, MAX_ELEV)
        elif action == 5:
            self.current_azim = np.mod(self.current_azim + DELTA_AZIM, 360)
            self.current_elev = np.maximum(self.current_elev - DELTA_ELE, MIN_ELEV)
        elif action == 6:
            self.current_azim = np.mod(self.current_azim - DELTA_AZIM, 360)
            self.current_elev = np.minimum(self.current_elev + DELTA_ELE, MAX_ELEV)
        elif action == 7:
            self.current_azim = np.mod(self.current_azim - DELTA_AZIM, 360)
            self.current_elev = np.maximum(self.current_elev - DELTA_ELE, MIN_ELEV)
        # elif action == 8:
        #    pass ## camera don't move
        else:
            raise Exception('bad action')

        if nolimit:
            self.current_azim = np.random.choice(azim_all)
            self.current_elev = np.random.choice(elev_all)

        self.step_count += 1
        if self.step_count == self.max_episode_length - 1:
            done = True
        else:
            done = False

        return [self.prev_azims, self.prev_elevs], [self.current_azim, self.current_elev], done, self.current_model

# Not used
class trajectData():
    def __init__(self, states, actions, rewards, model_id):
        self.states = states
        self.actions = actions
        self.rewards = rewards
        self.model_id = model_id
