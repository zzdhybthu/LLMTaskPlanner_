import os
import json
import time
from omegaconf import OmegaConf
from typing import List
import logging

from src.tdw.tdw_agent import TdwAgent
from src.tdw.tdw_env import TDW

# gym.envs.registration.register(
#     id='transport_challenge_MA',
#     entry_point='src/tdw/tdw_env:TDW'
# )


# def init_logs(output_dir, name = 'simple_example'):
#     logger = logging.getLogger(name)
#     logger.setLevel(logging.DEBUG)
#     fh = logging.FileHandler(os.path.join(output_dir, "output.log"))
#     fh.setLevel(logging.DEBUG)
#     ch = logging.StreamHandler()
#     ch.setLevel(logging.INFO)

#     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     fh.setFormatter(formatter)
#     ch.setFormatter(formatter)
#     logger.addHandler(fh)
#     logger.addHandler(ch)
#     return logger

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class TdwEvaluator(object):
    def __init__(self, cfg):
        log.info(OmegaConf.to_yaml(cfg))
        self.cfg = cfg
        
        self.number_of_agents = len(cfg.agents)
        log.info(f"Number of agents: {self.number_of_agents}")
        self.port = cfg.port
        self.gt_mask = cfg.gt_mask
        self.max_frames = cfg.max_frames
        self.save_img = cfg.save_img
        
        os.makedirs(cfg.result_path, exist_ok = True)
        cfg.result_path = os.path.join(cfg.result_path, cfg.experiment_name)
        os.makedirs(cfg.result_path, exist_ok = True)
        cfg.result_path = os.path.join(cfg.result_path, cfg.run_id)
        os.makedirs(cfg.result_path, exist_ok = True)
        self.output_dir = cfg.result_path

    def evaluate(self):
        # self.env: TDW = gym.make("transport_challenge_MA", port=self.port, number_of_agents=self.number_of_agents, save_dir=self.output_dir, max_frames=self.max_frames, launch_build=self.cfg.launch_build, screen_size=self.cfg.screen_size, data_prefix=self.cfg.data_prefix, gt_mask=self.gt_mask)
        self.env = TDW(port=self.port, number_of_agents=self.number_of_agents, save_dir=self.output_dir, max_frames=self.max_frames, launch_build=self.cfg.launch_build, screen_size=self.cfg.screen_size, data_prefix=self.cfg.data_prefix, gt_mask=self.gt_mask)
        log.info(f'port:{self.port}')
        log.info("Environment Created")
        
        log.info(f"Loading data from {os.path.join(self.cfg.data_prefix, self.cfg.data_path)}")
        self.data = json.load(open(os.path.join(self.cfg.data_prefix, self.cfg.data_path), "r"))
        log.info("Loading done")
        
        agents = []
        for i in range(self.number_of_agents):
            agents.append(TdwAgent(agent_id=i, max_frames=self.max_frames, output_dir=self.output_dir, cfg=self.cfg))
        try:
            self.evaluate_main(agents, self.cfg.eval_episodes)
        finally:
            self.close()
    
    def evaluate_main(self, agents: List[TdwAgent], eval_episodes: List[int]):
        log.info('Evalute main!')
        total_frame = 0
        total_finish = 0.0
        log.info(f'Eval episodes are: {eval_episodes}')
        if eval_episodes[0] == -1:
            eval_episodes = range(len(self.data))
        num_eval_episodes = len(eval_episodes)
        log.info(f'Number of episodes to evaluate: {num_eval_episodes}')

        start = time.time()
        results = {}
        for i, episode in enumerate(eval_episodes):
            start_time = time.time()
            if os.path.exists(os.path.join(self.output_dir, str(episode), 'result_episode.json')):
                with open(os.path.join(self.output_dir, str(episode), 'result_episode.json'), 'r') as f:
                    result = json.load(f)
                total_finish += result['finish'] / result['total']
                results[episode] = result
                continue
            # The episode has been evaluated before

            if not os.path.exists(os.path.join(self.output_dir, str(episode))):
                os.makedirs(os.path.join(self.output_dir, str(episode)))
            log.info('Episode {} ({}/{})'.format(episode, i + 1, num_eval_episodes))
            log.info(f"Resetting Environment ... data is {self.data[episode]}")
            state, info, env_api = self.env.reset(seed=self.data[episode]['seed'], options=self.data[episode], output_dir = os.path.join(self.output_dir, str(episode)))
            for id, agent in enumerate(agents):
                if type(env_api) == list:
                    curr_api = env_api[id]
                else:
                    curr_api = env_api
                if info['goal_description'] is not None:
                    if agent.agent_type == 'lm_agent':
                        agent.reset(obs = state[str(id)], goal_objects = info['goal_description'], output_dir = os.path.join(self.output_dir, str(episode)), env_api = curr_api, agent_color = info['agent_colors'][id], agent_id = id, rooms_name=info['rooms_name'], gt_mask = self.gt_mask, save_img = self.save_img)
                    else:
                        log.error(f"Agent type {agent.agent_type} not supported")
                else:
                    agent.reset(output_dir = os.path.join(self.output_dir, str(episode)))
            log.info(f"Environment Reset. Took {time.time() - start_time} secs")
            local_finish = self.env.check_goal()
            done = False
            step_num = 0
            local_reward = 0.0
            
            while not done:
                step_num += 1
                actions = {}
                if self.save_img:
                    self.env.save_images(os.path.join(self.output_dir, str(episode), 'Images'))
                for agent_id, agent in enumerate(agents):
                    action = agent.act(state[str(agent_id)])
                    actions[str(agent_id)] = action
                state, reward, done, info = self.env.step(actions)
                local_reward += reward
                local_finish = self.env.check_goal()
                log.info(f"Episode: {episode}, Step: {step_num}, Reward: {local_reward}, Finish: {local_finish}, Frame: {self.env.num_frames}")
                if done:
                    break
            frame = self.env.num_frames
            total_frame += frame
            total_finish += local_finish[0] / local_finish[1]
            result = {
                "finish": local_finish[0],
                "total": local_finish[1],
                "frame": frame,
                "action_history": [{f"agent{i}": agent.action_history} for i, agent in enumerate(agents)],
            }
            log.info(f"Episode {episode} done. Finish: {local_finish[0]}/{local_finish[1]}")
            with open(os.path.join(self.output_dir, str(episode), 'result_episode.json'), 'w') as f:
                json.dump(result, f, indent=4)
            results[episode] = result
        avg_finish = total_finish / num_eval_episodes
        avg_frame = total_frame / num_eval_episodes
        final_results = {
            "avg_finish": avg_finish,
            "avg_frame": avg_frame,
            "episode_results": results,
        }
        with open(os.path.join(self.output_dir, 'eval_result.json'), 'w') as f:
            json.dump(final_results, f, indent=4)
        log.info(f'Eval done, avg transport rate {avg_finish}')
        log.info('Time: {}'.format(time.time() - start))
        return avg_finish
    
    def close(self):
        self.env.close()