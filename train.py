#!/usr/bin/env python2

import numpy as np

np.set_printoptions(precision=4)
import torch
import os
import sys
import time
import scipy.io as sio
from utils import logger
import other

log_string = logger.log_string

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'models'))
sys.path.append(os.path.join(BASE_DIR, 'utils'))
sys.path.append(os.path.join(BASE_DIR, 'env_data'))
import utils.tf_util as tf_util

# from visualizers import VisVox
from active_mvnet_tf import ActiveMVnet, SingleInput, MVInputs, batch_to_single_mvinput
from shapenet_env import ShapeNetEnv
from replay_memory import ReplayMemory, trajectData

from rollout import Rollout

np.random.seed(0)
torch.manual_seed(0)
global FLAGS
flags = tf.flags


flags.DEFINE_integer('burnin_start_iter', 0, '0 [default: 0]')
flags.DEFINE_integer('burn_in_iter', 10, 'burn in iteration for MVnet')
flags.DEFINE_boolean('reproj_mode', False, '')




flags.DEFINE_integer('gpu', 0, "GPU to use [default: GPU 0]")
# task and control (yellow)
flags.DEFINE_string('model_file', 'pcd_ae_1_lmdb', 'Model name')
flags.DEFINE_string('cat_name', 'airplane', 'Category name')
flags.DEFINE_string('category', '02958343', 'category Index')
flags.DEFINE_string('train_filename_prefix', 'train', '')
flags.DEFINE_string('val_filename_prefix', 'val', '')
flags.DEFINE_string('test_filename_prefix', 'test', '')
flags.DEFINE_float('delta', 10.0, 'angle of each movement')
# flags.DEFINE_string('LOG_DIR', '/newfoundland/rz1/log/summary', 'Log dir [default: log]')
flags.DEFINE_string('LOG_DIR', './log_agent', 'Log dir [default: log]')
flags.DEFINE_string('data_path', './data/lmdb', 'data directory')
flags.DEFINE_string('data_file', 'rgb2depth_single_0212', 'data file')
# flags.DEFINE_string('CHECKPOINT_DIR', '/newfoundland/rz1/log', 'Log dir [default: log]')
flags.DEFINE_string('CHECKPOINT_DIR', './log_agent', 'Log dir [default: log]')
flags.DEFINE_integer('max_ckpt_keeps', 10, 'maximal keeps for ckpt file [default: 10]')
flags.DEFINE_string('task_name', 'tmp', 'task name to create under /LOG_DIR/ [default: tmp]')
flags.DEFINE_boolean('restore', False, 'If resume from checkpoint')
flags.DEFINE_integer('restore_iter', 0, '')
flags.DEFINE_boolean('pretrain_restore', False, 'If resume from checkpoint')
flags.DEFINE_string('pretrain_restore_path', 'log_agent/pretrain_models/pretrain_model.ckpt-5', '')
flags.DEFINE_string('ae_file', '', '')
flags.DEFINE_boolean('use_gt', True, '')
# train (green)
flags.DEFINE_integer('num_point', 2048, 'Point Number [256/512/1024/2048] [default: 1024]')
flags.DEFINE_integer('resolution', 128, '')
flags.DEFINE_integer('voxel_resolution', 64, '')
flags.DEFINE_string('opt_step_name', 'opt_step', '')
flags.DEFINE_string('loss_name', 'sketch_loss', '')
flags.DEFINE_integer('batch_size', 4, 'Batch Size during training [default: 32]')
flags.DEFINE_float('learning_rate', 1e-3, 'Initial learning rate [default: 0.001]')  # used to be 3e-5
flags.DEFINE_float('momentum', 0.95, 'Initial learning rate [default: 0.9]')
flags.DEFINE_string('optimizer', 'adam', 'adam or momentum [default: adam]')
flags.DEFINE_integer('decay_step', 5000000, 'Decay step for lr decay [default: 200000]')
flags.DEFINE_float('decay_rate', 0.7, 'Decay rate for lr decay [default: 0.8]')
flags.DEFINE_integer('max_iter', 1000000, 'Decay step for lr decay [default: 200000]')
# arch (magenta)
flags.DEFINE_string('network_name', 'ae', 'Name for network architecture used for rgb to depth')

flags.DEFINE_string('unet_name', 'U_SAME', '')
# options: U_SAME, OUTLINE
flags.DEFINE_string('agg_name', 'GRU', '')
# options: GRU, OUTLINE

flags.DEFINE_integer('agg_channels', 16, 'agg_channels')

flags.DEFINE_boolean('if_deconv', True, 'If add deconv output to generator aside from fc output')
flags.DEFINE_boolean('if_constantLr', True, 'If use constant lr instead of decaying one')
flags.DEFINE_boolean('if_en_bn', True, 'If use batch normalization for the mesh decoder')
flags.DEFINE_boolean('if_gen_bn', False, 'If use batch normalization for the mesh generator')
flags.DEFINE_boolean('if_bn', False, 'If use batch normalization for the mesh decoder')
flags.DEFINE_boolean('if_dqn_bn', True, 'If use batch normalization for the mesh decoder')
flags.DEFINE_float('bn_decay', 0.95, 'Decay rate for batch normalization [default: 0.9]')
flags.DEFINE_boolean("if_transform", False, "if use two transform layers")
flags.DEFINE_float('reg_weight', 0.1, 'Reweight for mat loss [default: 0.1]')
flags.DEFINE_boolean("if_vae", False, "if use VAE instead of vanilla AE")
flags.DEFINE_boolean("if_l2Reg", False, "if use l2 regularizor for the generator")
flags.DEFINE_boolean("if_dqn_l2Reg", False, "if use l2 regularizor for the policy network")
flags.DEFINE_float('vae_weight', 0.1, 'Reweight for mat loss [default: 0.1]')
flags.DEFINE_boolean('use_gan', False, 'if using GAN [default: False]')
flags.DEFINE_boolean('use_coef', False, 'if use coefficient for loss')
flags.DEFINE_float('loss_coef', 10, 'Coefficient for reconstruction loss [default: 10]')
flags.DEFINE_float('reward_weight', 10, 'rescale factor for reward value [default: 10]')
flags.DEFINE_float('penalty_weight', 0.0005, 'rescale factor for reward value [default: 10]')
flags.DEFINE_float('reg_act', 0.1, 'Reweight for mat loss [default: 0.1]')
flags.DEFINE_float('iou_thres', 0.4, 'Reweight for computing iou [default: 0.5]')
flags.DEFINE_boolean('random_pretrain', False, 'if random pretrain mvnet')
flags.DEFINE_integer('burin_opt', 0, '0: on all, 1: on last, 2: on first [default: 0]')
flags.DEFINE_boolean('dqn_use_rgb', True, 'use rgb for dqn')
flags.DEFINE_boolean('finetune_dqn', False, 'use rgb for dqn')
flags.DEFINE_boolean('finetune_dqn_only', False, 'use rgb for dqn')
flags.DEFINE_string('explore_mode', 'active', '')
flags.DEFINE_string('burnin_mode', 'random', '')
flags.DEFINE_boolean("use_critic", False, "if save evaluation results")
flags.DEFINE_boolean("debug_train", False, "if save evaluation results")
flags.DEFINE_boolean("occu_only", False, "Not using rgb value")
flags.DEFINE_boolean("sparse_mask", False, "Not using rgb value")
# log and drawing (blue)
flags.DEFINE_boolean("is_training", True, 'training flag')
flags.DEFINE_boolean("force_delete", False, "force delete old logs")
flags.DEFINE_boolean("if_summary", True, "if save summary")
flags.DEFINE_boolean("if_save", True, "if save")
flags.DEFINE_integer("save_every_step", 10, "save every ? step")
flags.DEFINE_boolean("if_test", True, "if test")
flags.DEFINE_integer("test_every_step", 2, "test every ? step")
flags.DEFINE_boolean("if_draw", True, "if draw latent")
flags.DEFINE_integer("draw_every_step", 1000, "draw every ? step")
flags.DEFINE_integer("vis_every_step", 1000, "draw every ? step")
flags.DEFINE_boolean("if_init_i", False, "if init i from 0")
flags.DEFINE_integer("init_i_to", 1, "init i to")
flags.DEFINE_integer("test_iter", 2, "init i to")
flags.DEFINE_integer("test_episode_num", 2, "init i to")
flags.DEFINE_boolean("save_test_results", True, "if init i from 0")
flags.DEFINE_boolean("if_save_eval", False, "if save evaluation results")
flags.DEFINE_boolean("initial_dqn", False, "if initial dqn")
# reinforcement learning
flags.DEFINE_integer('mvnet_resolution', 224, 'image resolution for mvnet')
flags.DEFINE_integer('max_episode_length', 6, 'maximal episode length for each trajactory')
flags.DEFINE_integer('mem_length', 1000, 'memory length for replay memory')
flags.DEFINE_integer('action_num', 8, 'number of actions')
flags.DEFINE_integer('burn_in_length', 10, 'burn in length for replay memory')
flags.DEFINE_string('reward_type', 'IoU', 'reward type: [IoU, IG]')
flags.DEFINE_float('init_eps', 0.95, 'initial value for epsilon')
flags.DEFINE_float('end_eps', 0.05, 'initial value for epsilon')
flags.DEFINE_float('epsilon', 0, 'epsilon')
flags.DEFINE_float('gamma', 0.99, 'discount factor for reward')
flags.DEFINE_boolean('debug_single', False, 'debug mode: using single model')
flags.DEFINE_boolean('debug_mode', False, '')
# whether to introduce pose noise to the unprojection
flags.DEFINE_boolean('pose_noise', False, '')
flags.DEFINE_string('seg_cluster_mode', 'kcenters', '')
flags.DEFINE_string('seg_decision_rule', 'with_occ', '')
flags.DEFINE_boolean('eval0', False, '')

# some constants i moved inside
flags.DEFINE_float('BN_INIT_DECAY', 0.5, '')
flags.DEFINE_float('BN_DECAY_DECAY_RATE', 0.5, '')
flags.DEFINE_float('BN_DECAY_DECAY_STEP', -1, '')
flags.DEFINE_float('BN_DECAY_CLIP', 0.99, '')

FLAGS = flags.FLAGS

FLAGS.BN_DECAY_DECAY_STEP = float(FLAGS.decay_step)


def save(ae, step, epoch, batch):
    ckpt_dir = get_restore_path()
    if not os.path.exists(FLAGS.LOG_DIR):
        os.mkdir(FLAGS.LOG_DIR)
    if not os.path.exists(ckpt_dir):
        os.mkdir(ckpt_dir)
    saved_checkpoint = ae.saver.save(ae.sess, \
                                     os.path.join(ckpt_dir, 'model.ckpt'), global_step=step)
    log_string(tf_util.toBlue("-----> Model saved to file: %s; step = %d" % (saved_checkpoint, step)))


def save_pretrain(ae, step):
    ckpt_dir = get_restore_path()
    if not os.path.exists(FLAGS.LOG_DIR):
        os.mkdir(FLAGS.LOG_DIR)
    if not os.path.exists(ckpt_dir):
        os.mkdir(ckpt_dir)
    saved_checkpoint = ae.pretrain_saver.save(ae.sess, \
                                              os.path.join(ckpt_dir, 'pretrain_model.ckpt'), global_step=step)
    log_string(tf_util.toBlue("-----> Pretrain Model saved to file: %s; step = %d" % (saved_checkpoint, step)))


def get_restore_path():
    return os.path.join(FLAGS.LOG_DIR, FLAGS.CHECKPOINT_DIR)


def restore(ae):
    restore_path = get_restore_path()
    latest_checkpoint = tf.train.latest_checkpoint(restore_path)
    log_string(tf_util.toYellow("----#-> Model restoring from: %s..." % restore_path))
    ae.saver.restore(ae.sess, latest_checkpoint)
    log_string(tf_util.toYellow("----- Restored from %s." % latest_checkpoint))


def restore_pretrain(ae):
    restore_path = FLAGS.pretrain_restore_path
    log_string(tf_util.toYellow("----#-> Model restoring from: %s..." % restore_path))
    ae.pretrain_saver.restore(ae.sess, restore_path)
    log_string(tf_util.toYellow("----- Restored from %s." % restore_path))


def restore_from_iter(ae, iter):
    restore_path = get_restore_path()
    ckpt_path = os.path.join(restore_path, 'model.ckpt-{0}'.format(iter))
    print(tf_util.toYellow("----#-> Model restoring from: {} using {} iterations...".format(restore_path, iter)))
    ae.saver.restore(ae.sess, ckpt_path)
    print(tf_util.toYellow("----- Restored from %s." % ckpt_path))


def burnin_log(i, out_stuff, t):
    recon_loss = out_stuff.recon_loss
    critic_loss = out_stuff.critic_loss
    seg_loss = 0.0
    reproj_loss = out_stuff.reproj_train_loss if FLAGS.burin_opt == 3 else 0.0
    log_string(
        'Burn in iter: {}, recon_loss: {:.4f}, critic_loss: {:.4f}, seg_loss: {:.4f}, reproj_loss: {:.4f}, unproject time: {:.2f}s'.format(
            i, recon_loss, critic_loss, seg_loss, reproj_loss, t))

    summary_recon = tf.Summary(value=[tf.Summary.Value(tag='burin/loss_recon', simple_value=recon_loss)])
    summary_critic = tf.Summary(value=[tf.Summary.Value(tag='burin/critic_loss', simple_value=critic_loss)])
    return [summary_recon, summary_critic]


def train_log(i, out_stuff, t):
    recon_loss = out_stuff.recon_loss / (FLAGS.max_episode_length * FLAGS.batch_size)
    reinforce_loss = out_stuff.loss_reinforce
    loss_act_reg = out_stuff.loss_act_regu

    mean_episode_reward = np.mean(np.sum(out_stuff.reward_raw_batch, axis=1), axis=0)
    log_string(
        'Iter: {}, recon_loss: {:.4f}, mean_episode_reward: {}, reinforce_loss: {}, reg_act: {}, time: {}, {}, {}'.format(
            i, recon_loss, mean_episode_reward, reinforce_loss, loss_act_reg, t[1] - t[0], t[2] - t[1], t[3] - t[2],
        )
    )


def eval_log(i, out_stuff, iou):
    reward = np.sum(out_stuff.reward_raw_test)
    losses = out_stuff.recon_loss_list_test
    log_string('------Episode: {}, episode_reward: {:.4f}, IoU: {:.4f}, Losses: {}------'.format(
        i, reward, iou, losses))


def run_step(mvnet_input, mode, is_training=True):
    active_mv()



def train(active_mv):
    senv = ShapeNetEnv(FLAGS)
    replay_mem = ReplayMemory(FLAGS)

    log_string('====== Starting burning in memories ======')
    burn_in(senv, replay_mem)
    log_string('====== Done. {} trajectories burnt in ======'.format(FLAGS.burn_in_length))

    rollout_obj = Rollout(active_mv, senv, replay_mem, FLAGS)
    # burn in(pretrain) for MVnet
    if FLAGS.burn_in_iter > 0:
        for i in range(FLAGS.burnin_start_iter, FLAGS.burnin_start_iter + FLAGS.burn_in_iter):

            rollout_obj.go(i, verbose=True, add_to_mem=True, mode=FLAGS.burnin_mode, is_train=True)
            mvnet_input = replay_mem.get_batch_list(FLAGS.batch_size)

            tic = time.time()
            out_stuff = run_step(mvnet_input, mode='burnin', is_training=True)

            if (i + 1) % FLAGS.save_every_step == 0 and i > FLAGS.burnin_start_iter:
                save_pretrain(active_mv, i + 1)

            if (((i + 1) % FLAGS.test_every_step == 0 and i > FLAGS.burnin_start_iter) or
                    (FLAGS.eval0 and i == FLAGS.burnin_start_iter)):
                evaluate_burnin(active_mv, FLAGS.test_episode_num, replay_mem, i + 1, rollout_obj,
                                mode=FLAGS.burnin_mode,
                                override_mvnet_input=(batch_to_single_mvinput(mvnet_input)
                                                      if FLAGS.reproj_mode else None))

    for i_idx in range(FLAGS.max_iter):

        t0 = time.time()

        if np.random.uniform() < FLAGS.epsilon:
            rollout_obj.go(i_idx, verbose=True, add_to_mem=True, mode=FLAGS.explore_mode, is_train=True)
        else:
            rollout_obj.go(i_idx, verbose=True, add_to_mem=True, is_train=True)
        t1 = time.time()

        mvnet_input = replay_mem.get_batch_list(FLAGS.batch_size)
        t2 = time.time()

        out_stuff = active_mv.run_step(mvnet_input, mode='train', is_training=True)
        t3 = time.time()

        train_log(i_idx, out_stuff, (t0, t1, t2, t3))

        if (i_idx + 1) % FLAGS.save_every_step == 0 and i_idx > 0:
            save(active_mv, i_idx + 1, i_idx + 1, i_idx + 1)

        if (i_idx + 1) % FLAGS.test_every_step == 0 and i_idx > 0:
            print('Evaluating active policy')
            evaluate(active_mv, FLAGS.test_episode_num, replay_mem, i_idx + 1, rollout_obj, mode='active')
            print('Evaluating random policy')
            evaluate(active_mv, FLAGS.test_episode_num, replay_mem, i_idx + 1, rollout_obj, mode='oneway')


def evaluate(active_mv, test_episode_num, replay_mem, train_i, rollout_obj, mode='active'):
    senv = ShapeNetEnv(FLAGS)

    # epsilon = FLAGS.init_eps
    rewards_list = []
    IoU_list = []
    loss_list = []

    for i_idx in range(test_episode_num):

        ## use active policy
        mvnet_input, actions = rollout_obj.go(i_idx, verbose=False, add_to_mem=False, mode=mode, is_train=False)
        # stop_idx = np.argwhere(np.asarray(actions)==8) ## find stop idx
        # if stop_idx.size == 0:
        #    pred_idx = -1
        # else:
        #    pred_idx = stop_idx[0, 0]

        model_id = rollout_obj.env.current_model
        voxel_name = os.path.join('voxels', '{}/{}.mat'.format(FLAGS.category, model_id))
        if FLAGS.category == '1111':
            category_, model_id_ = model_id.split('/')
            voxel_name = os.path.join('voxels', '{}/{}/model.binvox'.format(category_, model_id_))
        vox_gt = replay_mem.read_vox(voxel_name)

        mvnet_input.put_voxel(vox_gt)
        pred_out = active_mv.predict_vox_list(mvnet_input)

        vox_gtr = np.squeeze(pred_out.rotated_vox_test)

        PRINT_SUMMARY_STATISTICS = False
        if PRINT_SUMMARY_STATISTICS:
            lastpred = pred_out.vox_pred_test[-1]
            print
            'prediction statistics'
            print
            'min', np.min(lastpred)
            print
            'max', np.max(lastpred)
            print
            'mean', np.mean(lastpred)
            print
            'std', np.std(lastpred)

        # final_IoU = replay_mem.calu_IoU(pred_out.vox_pred_test[-1], vox_gtr)
        final_IoU = replay_mem.calu_IoU(pred_out.vox_pred_test[-1], vox_gtr, FLAGS.iou_thres)
        eval_log(i_idx, pred_out, final_IoU)

        rewards_list.append(np.sum(pred_out.reward_raw_test))
        IoU_list.append(final_IoU)
        loss_list.append(np.mean(pred_out.recon_loss_list_test))

        if FLAGS.if_save_eval:
            save_dict = {
                'voxel_list': np.squeeze(pred_out.vox_pred_test),
                'voxel_rot_list': np.squeeze(pred_out.vox_pred_test_rot),
                'vox_gt': vox_gt,
                'vox_gtr': vox_gtr,
                'model_id': model_id,
                'states': rollout_obj.last_trajectory,
                'RGB_list': mvnet_input.rgb
            }

            dump_outputs(save_dict, train_i, i_idx, mode)

    rewards_list = np.asarray(rewards_list)
    IoU_list = np.asarray(IoU_list)
    loss_list = np.asarray(loss_list)

    eval_r_mean = np.mean(rewards_list)
    eval_IoU_mean = np.mean(IoU_list)
    eval_loss_mean = np.mean(loss_list)
    eval_r_std = np.std(rewards_list) / len(rewards_list) ** 0.5
    eval_IoU_std = np.std(IoU_list) / len(IoU_list) ** 0.5
    eval_loss_std = np.std(loss_list) / len(loss_list) ** 0.5

    print
    'eval_r_mean is', eval_r_mean
    print
    'eval_iou_mean is', eval_IoU_mean
    print
    'eval_loss_mean is', eval_loss_mean
    print
    'eval_r_stderr is', eval_r_std
    print
    'eval_iou_stderr is', eval_IoU_std
    print
    'eval_loss_stderr is', eval_loss_std

    tf_util.save_scalar(train_i, 'eval_mean_reward_{}'.format(mode), eval_r_mean, active_mv.train_writer)
    tf_util.save_scalar(train_i, 'eval_mean_IoU_{}'.format(mode), eval_IoU_mean, active_mv.train_writer)
    tf_util.save_scalar(train_i, 'eval_mean_loss_{}'.format(mode), eval_loss_mean, active_mv.train_writer)


def evaluate_burnin(active_mv, test_episode_num, replay_mem, train_i, rollout_obj,
                    mode='random', override_mvnet_input=None):
    senv = ShapeNetEnv(FLAGS)

    # epsilon = FLAGS.init_eps
    rewards_list = []
    IoU_list = []
    loss_list = []

    for i_idx in range(test_episode_num):

        ## use active policy
        mvnet_input, actions = rollout_obj.go(i_idx, verbose=False, add_to_mem=False, mode=mode, is_train=False)
        # stop_idx = np.argwhere(np.asarray(actions)==8) ## find stop idx
        # if stop_idx.size == 0:
        #    pred_idx = -1
        # else:
        #    pred_idx = stop_idx[0, 0]

        model_id = rollout_obj.env.current_model
        voxel_name = os.path.join('voxels', '{}/{}.mat'.format(FLAGS.category, model_id))
        if FLAGS.category == '1111':
            category_, model_id_ = model_id.split('/')
            voxel_name = os.path.join('voxels', '{}/{}.mat'.format(category_, model_id_))
        vox_gt = replay_mem.read_vox(voxel_name)

        mvnet_input.put_voxel(vox_gt)

        if override_mvnet_input is not None:
            mvnet_input = override_mvnet_input

        pred_out = active_mv.predict_vox_list(mvnet_input)

        vox_gtr = np.squeeze(pred_out.rotated_vox_test)

        PRINT_SUMMARY_STATISTICS = False
        if PRINT_SUMMARY_STATISTICS:
            lastpred = pred_out.vox_pred_test[-1]
            print
            'prediction statistics'
            print
            'min', np.min(lastpred)
            print
            'max', np.max(lastpred)
            print
            'mean', np.mean(lastpred)
            print
            'std', np.std(lastpred)

        # final_IoU = replay_mem.calu_IoU(pred_out.vox_pred_test[-1], vox_gtr)
        final_IoU = replay_mem.calu_IoU(pred_out.vox_pred_test[-1], vox_gtr, FLAGS.iou_thres)
        eval_log(i_idx, pred_out, final_IoU)

        rewards_list.append(np.sum(pred_out.reward_raw_test))
        IoU_list.append(final_IoU)
        loss_list.append(np.mean(pred_out.recon_loss_list_test))

        # import ipdb
        # ipdb.set_trace()

        if FLAGS.if_save_eval:

            save_dict = {
                'voxel_list': np.squeeze(pred_out.vox_pred_test),
                'vox_gt': vox_gt,
                'vox_gtr': vox_gtr,
                'model_id': model_id,
                'states': rollout_obj.last_trajectory,
                'RGB_list': mvnet_input.rgb,
            }

            dump_outputs(save_dict, train_i, i_idx, mode)

    rewards_list = np.asarray(rewards_list)
    IoU_list = np.asarray(IoU_list)
    loss_list = np.asarray(loss_list)

    eval_r_mean = np.mean(rewards_list)
    eval_IoU_mean = np.mean(IoU_list)
    eval_loss_mean = np.mean(loss_list)

    tf_util.save_scalar(train_i, 'burnin_eval_mean_reward_{}'.format(mode), eval_r_mean, active_mv.train_writer)
    tf_util.save_scalar(train_i, 'burnin_eval_mean_IoU_{}'.format(mode), eval_IoU_mean, active_mv.train_writer)
    tf_util.save_scalar(train_i, 'burnin_eval_mean_loss_{}'.format(mode), eval_loss_mean, active_mv.train_writer)


def test(active_mv, test_episode_num, replay_mem, train_i, rollout_obj):
    senv = ShapeNetEnv(FLAGS)

    # epsilon = FLAGS.init_eps
    rewards_list = []
    IoU_list = []
    loss_list = []

    for i_idx in range(test_episode_num):

        mvnet_input, actions = rollout_obj.go(i_idx, verbose=False, add_to_mem=False, is_train=False, test_idx=i_idx)
        stop_idx = np.argwhere(np.asarray(actions) == 8)  ## find stop idx
        if stop_idx.size == 0:
            pred_idx = -1
        else:
            pred_idx = stop_idx[0, 0]

        model_id = rollout_obj.env.current_model
        voxel_name = os.path.join('voxels', '{}/{}/model.binvox'.format(FLAGS.category, model_id))
        if FLAGS.category == '1111':
            category_, model_id_ = model_id.split('/')
            voxel_name = os.path.join('voxels', '{}/{}/model.binvox'.format(category_, model_id_))
        vox_gt = replay_mem.read_vox(voxel_name)

        mvnet_input.put_voxel(vox_gt)
        pred_out = active_mv.predict_vox_list(mvnet_input)

        vox_gtr = np.squeeze(pred_out.rotated_vox_test)

        PRINT_SUMMARY_STATISTICS = False
        if PRINT_SUMMARY_STATISTICS:
            lastpred = pred_out.vox_pred_test[-1]
            print
            'prediction statistics'
            print
            'min', np.min(lastpred)
            print
            'max', np.max(lastpred)
            print
            'mean', np.mean(lastpred)
            print
            'std', np.std(lastpred)

        final_IoU = replay_mem.calu_IoU(pred_out.vox_pred_test[pred_idx], vox_gtr, FLAGS.iou_thres)
        eval_log(i_idx, pred_out, final_IoU)

        rewards_list.append(np.sum(pred_out.reward_raw_test))
        IoU_list.append(final_IoU)
        loss_list.append(pred_out.recon_loss_list_test)

        if FLAGS.if_save_eval:
            save_dict = {
                'voxel_list': np.squeeze(pred_out.vox_pred_test),
                'vox_gt': vox_gt,
                'vox_gtr': vox_gtr,
                'model_id': model_id,
                'states': rollout_obj.last_trajectory,
                'RGB_list': mvnet_input.rgb
            }

            dump_outputs(save_dict, train_i, i_idx)

    rewards_list = np.asarray(rewards_list)
    IoU_list = np.asarray(IoU_list)
    loss_list = np.asarray(loss_list)

    eval_r_mean = np.mean(rewards_list)
    eval_IoU_mean = np.mean(IoU_list)
    eval_loss_mean = np.mean(loss_list)

    tf_util.save_scalar(train_i, 'eval_mean_reward', eval_r_mean, active_mv.train_writer)
    tf_util.save_scalar(train_i, 'eval_mean_IoU', eval_IoU_mean, active_mv.train_writer)
    tf_util.save_scalar(train_i, 'eval_mean_loss', eval_loss_mean, active_mv.train_writer)


def burn_in(senv, replay_mem):
    tic = time.time()
    for i_idx in range(FLAGS.burn_in_length):
        if i_idx % 10 == 0 and i_idx != 0:
            toc = time.time()
            log_string('Burning in {}/{} sequences, time taken: {}s'.format(i_idx, FLAGS.burn_in_length, toc - tic))
            tic = time.time()
        state, model_id = senv.reset(True)
        actions = []
        RGB_temp_list = np.zeros((FLAGS.max_episode_length, FLAGS.resolution, FLAGS.resolution, 3), dtype=np.float32)
        R_list = np.zeros((FLAGS.max_episode_length, 3, 4), dtype=np.float32)

        RGB_temp_list[0, ...], _ = replay_mem.read_png_to_uint8(state[0][0], state[1][0], model_id)
        R_list[0, ...] = replay_mem.get_R(state[0][0], state[1][0])

        for e_idx in range(FLAGS.max_episode_length - 1):
            actions.append(np.random.randint(FLAGS.action_num))
            state, next_state, done, model_id = senv.step(actions[-1])
            RGB_temp_list[e_idx + 1, ...], _ = replay_mem.read_png_to_uint8(next_state[0], next_state[1], model_id)
            R_list[e_idx + 1, ...] = replay_mem.get_R(next_state[0], next_state[1])
            if done:
                traj_state = state
                traj_state[0] += [next_state[0]]
                traj_state[1] += [next_state[1]]
                temp_traj = trajectData(traj_state, actions, model_id)
                replay_mem.append(temp_traj)
                break


def dump_outputs(save_dict, train_i, i_idx, mode=''):
    eval_dir = os.path.join(FLAGS.LOG_DIR, 'eval')
    if not os.path.exists(eval_dir):
        os.mkdir(eval_dir)

    eval_dir = os.path.join(eval_dir, '{}'.format(train_i))
    if not os.path.exists(eval_dir):
        os.mkdir(eval_dir)

    mat_save_name = os.path.join(eval_dir, '{}_{}.mat'.format(i_idx, mode))
    sio.savemat(mat_save_name, save_dict)

    gt_save_name = os.path.join(eval_dir, '{}_gt.binvox'.format(i_idx))
    save_voxel(save_dict['vox_gt'], gt_save_name)

    gtr_save_name = os.path.join(eval_dir, '{}_gtr.binvox'.format(i_idx))
    save_voxel(save_dict['vox_gtr'], gtr_save_name)

    for i in range(FLAGS.max_episode_length):
        pred_save_name = os.path.join(eval_dir, '{}_pred{}_{}.binvox'.format(i_idx, i, mode))
        save_voxel(save_dict['voxel_list'][i], pred_save_name)

        img_save_name = os.path.join(eval_dir, '{}_rgb{}_{}.png'.format(i_idx, i, mode))
        other.img.imsave01(img_save_name, save_dict['RGB_list'][0, i])


def save_voxel(vox, pth):
    THRESHOLD = 0.5
    s = vox.shape[0]
    vox = np.transpose(vox, (2, 1, 0))
    binvox_obj = other.binvox_rw.Voxels(
        vox > THRESHOLD,
        dims=[s] * 3,
        translate=[0.0, 0.0, 0.0],
        scale=1.0,
        axis_order='xyz'
    )
    with open(pth, 'wb') as f:
        binvox_obj.write(f)


if __name__ == "__main__":
    FLAGS.LOG_DIR = FLAGS.LOG_DIR + '/' + FLAGS.task_name

    if not os.path.exists(FLAGS.LOG_DIR):
        os.mkdir(FLAGS.LOG_DIR)
        print
        tf_util.toYellow('===== Created %s.' % FLAGS.LOG_DIR)
    else:
        if not (FLAGS.restore):

            def check_delete():
                if FLAGS.force_delete:
                    return True
                delete_key = input(tf_util.toRed('===== %s exists. Delete? [y (or enter)/N] ' % FLAGS.LOG_DIR))
                return delete_key == 'y' or delete_key == ''


            if check_delete():
                os.system('rm -rf %s/*' % FLAGS.LOG_DIR)
                # os.system('rm -rf %s/*'%FLAGS.CHECKPOINT_DIR)
                print
                tf_util.toRed('Deleted.' + FLAGS.LOG_DIR)
            else:
                print
                tf_util.toRed('Overwrite.')
        else:
            print
            tf_util.toRed('To Be Restored...')

    logger.FLAGS.LOG_FOUT = open(os.path.join(FLAGS.LOG_DIR, 'log_train.txt'), 'w')
    logger.FLAGS.LOG_FOUT.write(str(FLAGS) + '\n')

    active_mv = ActiveMVnet(FLAGS)
    if FLAGS.restore:
        if FLAGS.restore_iter:
            restore_from_iter(active_mv, FLAGS.restore_iter)
        else:
            restore(active_mv)
    if FLAGS.pretrain_restore:
        restore_pretrain(active_mv)

    train(active_mv)

    FLAGS.LOG_FOUT.close()
