import numpy as np
import sklearn
from joblib import Parallel, delayed
from sklearn.cross_validation import cross_val_predict

__all__ = []


def _wrap_fit(x, y, pred):
    pred.fit(x, y)
    return pred


def _wrap_predict(x, pred):
    return pred.predict(x)


class Stacker(object):
    """
    Ensemble learning combining multiple regression models into a single regression pipeline.

    This class implements a two-staged stacker:
        The first stage Includes a list of estimators.
        The second stage include one estimator (the stacker) that trains on the outputs of the first stage estimators.

    The estimators are expected to be scikit-learn compatible, but can be complex Pipelines.

    Parameters
    ----------
        first_level_preds : list (of sklearn estimators / pipelines),
            lower-level estimators to stack.

        stacker_pred : sklearn estimator-like object,
            the meta-level model that trains on the first level estimators outputs

        cv_fn: function,
            a cross validation function to be used for the when fitting the stacker

        n_jobs: int, (default: 1)
            number of workers to use (for the cross validation as well as for parallel training)
            n_jobs=-1 means all available workers (by CPU cores) should used


    Examples
    --------
    """
    def __init__(
            self,
            first_level_preds,
            stacker_pred,
            cv_fn=lambda x: sklearn.cross_validation.LeaveOneOut(x.shape[0]),
            n_jobs=1):

        self._test_closed_cv_fn(cv_fn)
        self._first_level_preds = first_level_preds
        self._stacker_pred = stacker_pred
        self._cv_fn = cv_fn
        self._n_jobs = n_jobs

    def _test_closed_cv_fn(self, cv_fn):
        arr = np.array([i*i for i in range(1000)])
        cv_iterator = cv_fn(arr)
        lst = []
        for train, test in cv_iterator:
            lst.extend(list(test))

        if len(set(lst)) != len(arr):
            raise ValueError(
                'cv_fn:%s is not a closed cross validation function - not all values are covered'
                % cv_fn)

    def predict(self, x):
        """
        Same signature as any sklearn stage.

        method:
           1. The first stage estimators fit and predict the data and target using cross_val_predict.
           2. The meta-level estimator (stacker) is fitted by training over the outputs of the
              first stage estimators and trying to fit to the original target.
           3. Finally the first level estimators are re-fitted on the original data and target.

        """
        predict_results = Parallel(n_jobs=self._n_jobs)(delayed(_wrap_predict)(x, pred)
                                                        for pred in self._first_level_preds)
        return self._stacker_pred.predict(np.column_stack(tuple(predict_results)))

    def fit(self, x, y):
        """
        Same signature as any sklearn stage.

        method:
            1. The fitted first level estimators predict the target based on the data
            2. The fitted meta-level stacker predicts the target based on the outputs
               of the first level estimators.
        """
        cross_val_result = Parallel(n_jobs=self._n_jobs)(delayed(cross_val_predict)
                                                         (pred, X=x, y=y, cv=self._cv_fn(x))
                                                         for pred in self._first_level_preds)
        self._stacker_pred.fit(np.array(np.column_stack(tuple(cross_val_result))), y)
        result_preds = Parallel(n_jobs=self._n_jobs)(delayed(_wrap_fit)(x, y, pred)
                                                     for pred in self._first_level_preds)
        self._first_level_preds = result_preds
        return self


__all__ += ['Stacker']