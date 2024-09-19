import random
import numpy as np
import torch
import hydra
import logging

import sys
sys.path.insert(0, '.')


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg):
    log.info(cfg)

    # set random seed
    random.seed(cfg.planner.random_seed)
    torch.manual_seed(cfg.planner.random_seed)
    np.random.seed(cfg.planner.random_seed)

    if cfg.name == 'tdw':
        from src.tdw.tdw_evaluator import TdwEvaluator
        evaluator = TdwEvaluator(cfg)
    elif cfg.name == 'sllm':
        from src.sllm.sllm_evaluator import SllmEvaluator
        evaluator = SllmEvaluator(cfg)
    else:
        assert False
    evaluator.evaluate()


if __name__ == "__main__":
    main()
