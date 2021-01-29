from brownie import Wei

from helpers.token_utils import distribute_from_whales, distribute_test_ether
from scripts.systems.badger_system import BadgerSystem, connect_badger
from scripts.systems.badger_minimal import deploy_badger_minimal
from scripts.systems.constants import SettType
from scripts.deploy.upgrade import upgrade_versioned_proxy
from config.badger_config import badger_config
from rich.console import Console

console = Console()


class SettMiniDeployBase:
    def __init__(
        self,
        key,
        strategyName,
        deployer,
        strategist=None,
        governance=None,
        keeper=None,
        guardian=None,
    ):
        self.key = key
        self.strategyName = strategyName

        if not strategist:
            strategist = deployer
        if not governance:
            governance = deployer
        if not keeper:
            keeper = deployer
        if not guardian:
            guardian = deployer

        self.strategist = strategist
        self.governance = governance
        self.keeper = keeper
        self.guardian = guardian
        self.deployer = deployer

    def deploy(self, sett_type=SettType.DEFAULT, deploy=True, upgrade=False) -> BadgerSystem:
        if not deploy:
            self.badger = connect_badger(badger_config.prod_json)

            self.pre_deploy_setup(deploy=deploy)

            distribute_test_ether(self.deployer, Wei("20 ether"))
            distribute_from_whales(self.deployer)

            self.controller = self.badger.sett_system.controllers[self.key]
            self.vault = self.badger.sett_system.vaults[self.key]

            self.post_vault_deploy_setup(deploy=deploy)

            self.strategy = self.badger.sett_system.strategies[self.key]

            self.post_deploy_setup(deploy=deploy)

            if self.vault.paused():
                self.vault.unpause({"from": self.governance})

            if upgrade:
                self.upgrade_versioned()

            return self.badger

        self.badger = deploy_badger_minimal(self.deployer, self.keeper, self.guardian)
        self.controller = self.badger.add_controller(self.key)
        self.deploy_required_logic()

        self.pre_deploy_setup(deploy=deploy)

        (params, want) = self.fetch_params()

        self.params = params
        self.want = want

        distribute_test_ether(self.deployer, Wei("20 ether"))
        distribute_from_whales(self.deployer)

        self.controller = self.badger.add_controller(self.key)
        self.vault = self.badger.deploy_sett(
            self.key,
            self.want,
            self.controller,
            governance=self.governance,
            strategist=self.strategist,
            keeper=self.keeper,
            guardian=self.guardian,
            sett_type=sett_type,
        )

        self.post_vault_deploy_setup(deploy=deploy)
        print("Deploying Strategy with key: ", self.key)
        self.strategy = self.badger.deploy_strategy(
            self.key,
            self.strategyName,
            self.controller,
            self.params,
            governance=self.governance,
            strategist=self.strategist,
            keeper=self.keeper,
            guardian=self.guardian,
        )

        self.badger.wire_up_sett(self.vault, self.strategy, self.controller)

        self.post_deploy_setup(deploy=deploy)

        assert self.vault.paused()

        self.vault.unpause({"from": self.governance})

        return self.badger

    def deploy_required_logic(self):
        self.badger.deploy_core_logic()
        self.badger.deploy_sett_core_logic()
        self.badger.deploy_sett_strategy_logic_for(self.strategyName)

    # Upgrade versioned contracts if not up to date.
    # Currently the only versioned contracts are strategy/sett contracts.
    # NB: This must be run AFTER connecting to the badger system.
    def upgrade_versioned(self):
        badger = self.badger
        deployer = self.deployer
        for key, contract in badger.contracts_upgradeable.items():
            if key.removesuffix(".strategy").removesuffix(".sett") != self.key:
                continue

            if key.endswith(".strategy"):
                Artifact = badger.getStrategyArtifact(
                    key.removesuffix(".strategy")
                )
                latest = Artifact.deploy({"from": deployer})
                upgrade_versioned_proxy(
                    badger,
                    contract,
                    latest,
                )

            if key.endswith(".sett"):
                Artifact = badger.getSettArtifact(
                    key.removesuffix(".sett")
                )
                latest = Artifact.deploy({"from": deployer})
                upgrade_versioned_proxy(
                    badger,
                    contract,
                    latest,
                )

    # ===== Specific instance must implement =====
    def fetch_params(self):
        return False

    def pre_deploy_setup(self, deploy=True):
        return False

    def post_deploy_setup(self, deploy=True):
        return False

    def post_vault_deploy_setup(self, deploy=True):
        return False
