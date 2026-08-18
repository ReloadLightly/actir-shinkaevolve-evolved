"""Frozen train / dev / test world seeds.

Review point 8: held-out testing was underspecified. These seeds are fixed
here, in version control, BEFORE any optimisation runs, and they are hashed
into FROZEN.json alongside world.py.

Three disjoint banks, and the discipline that goes with them:

* **train** — where every baseline and every evolved policy is optimised.
* **dev** — for choosing between candidate designs, checking convergence, and
  any decision that would otherwise be made by peeking at the test set.
* **test** — touched ONCE, for the reported numbers. Every arm is scored on the
  identical bank, so comparisons are PAIRED: the same worlds, the same crisis
  draws, the same economic shocks. Paired differences have far tighter
  confidence intervals than unpaired means, which matters when the whole
  question is whether one arm beats another by more than noise.

The banks also mix structural forms, not only parameter draws, so a result that
depends on one functional form for the counterpart response shows up as such.

**STATUS: DRAFT.** Preregistered and hashed into FROZEN.json. Once the
qualification is reported these seeds stop changing; the test bank is touched
once.
"""

from __future__ import annotations

from typing import Dict, List

from world import STRUCTURES, WorldParams, world_bank

#: Bank seeds. Disjoint by construction and never reused across splits.
TRAIN_SEED = 20260819
DEV_SEED = 20260820
TEST_SEED = 20260821

#: Bank sizes. 200 test worlds is chosen so that a paired difference of ~0.15
#: model points is resolvable; three seeds, as the first design proposed, is
#: far too few for a headline claim and the review said so.
TRAIN_SIZE = 120
DEV_SIZE = 80
TEST_SIZE = 200

#: Repeats per world, to average the within-world stochasticity (crisis draws
#: and economic shocks) that is NOT part of the hidden parameter draw.
EPISODE_REPEATS = 3


def train_worlds() -> List[WorldParams]:
    return world_bank(TRAIN_SEED, TRAIN_SIZE)


def dev_worlds() -> List[WorldParams]:
    return world_bank(DEV_SEED, DEV_SIZE)


def test_worlds() -> List[WorldParams]:
    return world_bank(TEST_SEED, TEST_SIZE)


def split(name: str) -> List[WorldParams]:
    return {"train": train_worlds, "dev": dev_worlds, "test": test_worlds}[name]()


def describe() -> Dict[str, object]:
    return {
        "train": {"seed": TRAIN_SEED, "size": TRAIN_SIZE},
        "dev": {"seed": DEV_SEED, "size": DEV_SIZE},
        "test": {"seed": TEST_SEED, "size": TEST_SIZE},
        "episode_repeats": EPISODE_REPEATS,
        "structures": list(STRUCTURES),
    }
