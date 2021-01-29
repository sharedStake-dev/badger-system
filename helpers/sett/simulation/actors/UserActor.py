import random
from brownie import Sett, Controller
from typing import Any

from helpers.utils import approx
from helpers.constants import MaxUint256
from helpers.sett.SnapshotManager import SnapshotManager
from .BaseAction import BaseAction


class DepositAndWithdrawAction(BaseAction):
    def __init__(
        self,
        snap: SnapshotManager,
        user: Any,
        sett: Sett,
        want: Any,
    ):
        self.snap = snap
        self.user = user
        self.want = want
        self.sett = sett

    def run(self):
        user = self.user
        want = self.want
        sett = self.sett
        rewards = Controller.at(sett.controller()).rewards()

        beforeSettBalance = sett.balanceOf(user)
        startingBalance = want.balanceOf(user)
        depositAmount = startingBalance // 2
        assert startingBalance >= depositAmount
        assert startingBalance >= 0

        want.approve(
            self.sett,
            MaxUint256,
            {"from": user},
        )
        self.snap.settDeposit(
            depositAmount,
            {"from": user},
        )

        afterSettBalance = sett.balanceOf(user)
        settDeposited = afterSettBalance - beforeSettBalance
        beforeRewardsBalance = want.balanceOf(rewards)
        # Confirm that before and after balance does not exceed
        # max precision loss.
        self.snap.settWithdraw(settDeposited, {"from": self.user})
        rewardsDiff = want.balanceOf(rewards) - beforeRewardsBalance
        endingBalance = want.balanceOf(user)
        assert approx(
            startingBalance,
            endingBalance + rewardsDiff,
            1,
        )


class DepositAction(BaseAction):
    def __init__(
        self,
        snap: SnapshotManager,
        user: Any,
        sett: Sett,
        want: Any,
    ):
        self.snap = snap
        self.user = user
        self.want = want
        self.sett = sett

    def run(self):
        user = self.user
        want = self.want

        startingBalance = want.balanceOf(user)
        depositAmount = startingBalance // 2
        assert startingBalance >= depositAmount
        assert startingBalance >= 0

        want.approve(
            self.sett,
            MaxUint256,
            {"from": user},
        )
        self.snap.settDeposit(
            depositAmount,
            {"from": user},
        )


class WithdrawAction(BaseAction):
    def __init__(
        self,
        snap: SnapshotManager,
        user: Any,
    ):
        self.snap = snap
        self.user = user

    def run(self):
        self.snap.settWithdrawAll({"from": self.user})


class UserActor:
    def __init__(self, manager: Any, user: Any):
        self.snap = manager.snap
        self.sett = manager.sett
        self.want = manager.want
        self.user = user
        self.deposited = False

    def generateAction(self) -> BaseAction:
        '''
        Produces deposit -> withdraw -> deposit -> withdraw...
        ops for now and interleaved deposit/withdraw ops.
        '''
        # Randomly confirm deposit and withdraw in same action
        # does not exceed max precision loss. This can be interleaved
        # between the regular deposit -> withdraw flow.
        if random.random() > 0.5:
            return DepositAndWithdrawAction(
                self.snap,
                self.user,
                self.sett,
                self.want,
            )
        if self.deposited:
            self.deposited = False
            return WithdrawAction(
                self.snap,
                self.user,
            )
        self.deposited = True
        return DepositAction(
            self.snap,
            self.user,
            self.sett,
            self.want,
        )
