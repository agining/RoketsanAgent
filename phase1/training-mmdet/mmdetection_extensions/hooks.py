from mmengine.hooks import Hook
from mmengine.model import is_model_wrapper

from mmdet.registry import HOOKS


@HOOKS.register_module()
class FreezeModulesHook(Hook):
    """Freeze submodules (e.g. the backbone) until ``unfreeze_epoch``.

    While frozen, the modules' parameters get ``requires_grad=False`` (the
    optimizer skips parameters without gradients) and their BatchNorm layers
    are kept in eval mode, so running statistics stay at their pretrained
    values. From ``unfreeze_epoch`` on everything trains normally.

    Args:
        modules (list[str]): Submodule names, e.g. ``['backbone']``.
        unfreeze_epoch (int): First (0-based) epoch that trains them.
    """

    priority = 'NORMAL'

    def __init__(self, modules=('backbone', ), unfreeze_epoch=10):
        self.modules = list(modules)
        self.unfreeze_epoch = unfreeze_epoch
        self._frozen = None

    def _submodules(self, runner):
        model = runner.model
        if is_model_wrapper(model):
            model = model.module
        return [model.get_submodule(name) for name in self.modules]

    def before_train_epoch(self, runner):
        frozen = runner.epoch < self.unfreeze_epoch
        if frozen != self._frozen:
            for module in self._submodules(runner):
                for param in module.parameters():
                    param.requires_grad = not frozen
            runner.logger.info(
                f'{"Freezing" if frozen else "Unfreezing"} {self.modules} '
                f'at epoch {runner.epoch + 1}')
            self._frozen = frozen

    def before_train_iter(self, runner, batch_idx, data_batch=None):
        # model.train() runs after before_train_epoch, so put the frozen
        # modules (their BatchNorm) back into eval mode here
        if self._frozen:
            for module in self._submodules(runner):
                if module.training:
                    module.eval()
