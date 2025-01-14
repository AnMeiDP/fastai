# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/17_callback.tracker.ipynb (unless otherwise specified).


from __future__ import annotations


__all__ = ['TerminateOnNaNCallback', 'TrackerCallback', 'EarlyStoppingCallback', 'SaveModelCallback',
           'ReduceLROnPlateau']

# Cell
#nbdev_comment from __future__ import annotations
from ..basics import *
from .progress import *
from .fp16 import MixedPrecision

# Cell
class TerminateOnNaNCallback(Callback):
    "A `Callback` that terminates training if loss is NaN."
    order=-9
    def after_batch(self):
        "Test if `last_loss` is NaN and interrupts training."
        if torch.isinf(self.loss) or torch.isnan(self.loss): raise CancelFitException

# Cell
class TrackerCallback(Callback):
    "A `Callback` that keeps track of the best value in `monitor`."
    order,remove_on_fetch,_only_train_loop = 60,True,True
    def __init__(self,
        monitor='valid_loss', # value (usually loss or metric) being monitored.
        comp=None, # numpy comparison operator; np.less if monitor is loss, np.greater if monitor is metric.
        min_delta=0., # minimum delta between the last monitor value and the best monitor value.
        reset_on_fit=True # before model fitting, reset value being monitored to -infinity (if monitor is metric) or +infinity (if monitor is loss).
    ):
        if comp is None: comp = np.less if 'loss' in monitor or 'error' in monitor else np.greater
        if comp == np.less: min_delta *= -1
        self.monitor,self.comp,self.min_delta,self.reset_on_fit,self.best= monitor,comp,min_delta,reset_on_fit,None

    def before_fit(self):
        "Prepare the monitored value"
        self.run = not hasattr(self, "lr_finder") and not hasattr(self, "gather_preds")
        if self.reset_on_fit or self.best is None: self.best = float('inf') if self.comp == np.less else -float('inf')
        assert self.monitor in self.recorder.metric_names[1:]
        self.idx = list(self.recorder.metric_names[1:]).index(self.monitor)

    def after_epoch(self):
        "Compare the last value to the best up to now"
        val = self.recorder.values[-1][self.idx]
        if self.comp(val - self.min_delta, self.best): self.best,self.new_best = val,True
        else: self.new_best = False

    def after_fit(self): self.run=True

# Cell
class EarlyStoppingCallback(TrackerCallback):
    "A `TrackerCallback` that terminates training when monitored quantity stops improving."
    order=TrackerCallback.order+3
    def __init__(self,
        monitor='valid_loss', # value (usually loss or metric) being monitored.
        comp=None, # numpy comparison operator; np.less if monitor is loss, np.greater if monitor is metric.
        min_delta=0., # minimum delta between the last monitor value and the best monitor value.
        patience=1, # number of epochs to wait when training has not improved model.
        reset_on_fit=True # before model fitting, reset value being monitored to -infinity (if monitor is metric) or +infinity (if monitor is loss).
    ):
        super().__init__(monitor=monitor, comp=comp, min_delta=min_delta, reset_on_fit=reset_on_fit)
        self.patience = patience

    def before_fit(self): self.wait = 0; super().before_fit()
    def after_epoch(self):
        "Compare the value monitored to its best score and maybe stop training."
        super().after_epoch()
        if self.new_best: self.wait = 0
        else:
            self.wait += 1
            if self.wait >= self.patience:
                print(f'No improvement since epoch {self.epoch-self.wait}: early stopping')
                raise CancelFitException()

# Cell
class SaveModelCallback(TrackerCallback):
    "A `TrackerCallback` that saves the model's best during training and loads it at the end."
    order = TrackerCallback.order+1
    def __init__(self,
        monitor='valid_loss', # value (usually loss or metric) being monitored.
        comp=None, # numpy comparison operator; np.less if monitor is loss, np.greater if monitor is metric.
        min_delta=0., # minimum delta between the last monitor value and the best monitor value.
        fname='model', # model name to be used when saving model.
        every_epoch=False, # if true, save model after every epoch; else save only when model is better than existing best.
        at_end=False, # if true, save model when training ends; else load best model if there is only one saved model.
        with_opt=False, # if true, save optimizer state (if any available) when saving model.
        reset_on_fit=True # before model fitting, reset value being monitored to -infinity (if monitor is metric) or +infinity (if monitor is loss).
    ):
        super().__init__(monitor=monitor, comp=comp, min_delta=min_delta, reset_on_fit=reset_on_fit)
        assert not (every_epoch and at_end), "every_epoch and at_end cannot both be set to True"
        # keep track of file path for loggers
        self.last_saved_path = None
        store_attr('fname,every_epoch,at_end,with_opt')

    def _save(self, name): self.last_saved_path = self.learn.save(name, with_opt=self.with_opt)

    def after_epoch(self):
        "Compare the value monitored to its best score and save if best."
        if self.every_epoch:
            if (self.epoch%self.every_epoch) == 0: self._save(f'{self.fname}_{self.epoch}')
        else: #every improvement
            super().after_epoch()
            if self.new_best:
                print(f'Better model found at epoch {self.epoch} with {self.monitor} value: {self.best}.')
                self._save(f'{self.fname}')

    def after_fit(self, **kwargs):
        "Load the best model."
        if self.at_end: self._save(f'{self.fname}')
        elif not self.every_epoch: self.learn.load(f'{self.fname}', with_opt=self.with_opt)

# Cell
class ReduceLROnPlateau(TrackerCallback):
    "A `TrackerCallback` that reduces learning rate when a metric has stopped improving."
    order=TrackerCallback.order+2
    def __init__(self,
        monitor='valid_loss', # value (usually loss or metric) being monitored.
        comp=None, # numpy comparison operator; np.less if monitor is loss, np.greater if monitor is metric.
        min_delta=0., # minimum delta between the last monitor value and the best monitor value.
        patience=1, # number of epochs to wait when training has not improved model.
        factor=10., # the denominator to divide the learning rate by, when reducing the learning rate.
        min_lr=0, # the minimum learning rate allowed; learning rate cannot be reduced below this minimum.
        reset_on_fit=True # before model fitting, reset value being monitored to -infinity (if monitor is metric) or +infinity (if monitor is loss).
    ):
        super().__init__(monitor=monitor, comp=comp, min_delta=min_delta, reset_on_fit=reset_on_fit)
        self.patience,self.factor,self.min_lr = patience,factor,min_lr

    def before_fit(self): self.wait = 0; super().before_fit()
    def after_epoch(self):
        "Compare the value monitored to its best score and reduce LR by `factor` if no improvement."
        super().after_epoch()
        if self.new_best: self.wait = 0
        else:
            self.wait += 1
            if self.wait >= self.patience:
                old_lr = self.opt.hypers[-1]['lr']
                for h in self.opt.hypers: h['lr'] = max(h['lr'] / self.factor, self.min_lr)
                self.wait = 0
                if self.opt.hypers[-1]["lr"] < old_lr:
                    print(f'Epoch {self.epoch}: reducing lr to {self.opt.hypers[-1]["lr"]}')