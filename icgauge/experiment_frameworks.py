# -*- coding: utf-8 -*-
#!/usr/bin/python

from sklearn.feature_extraction import DictVectorizer
from sklearn.cross_validation import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from collections import Counter
from scipy.stats.stats import pearsonr

import data_readers
import feature_extractors as fe
import label_transformers as lt
import training_functions as training
import utils

# May eventually add other frameworks (e.g., neural network, rule-based)


def build_dataset(reader, phi_list, class_func, vectorizer=None, verbose=False):
    """Core general function for building experimental
    hand-generated feature datasets.
    
    Parameters
    ----------
    reader : iterator
       Should follow the format of data_readers. This is the dataset 
       we'll be featurizing.
       
    phi_list : array of feature functions (default: [`manual_content_flags`])
        Any function that takes a string as input and returns a 
        bool/int/float-valued dict as output.
       
    class_func : function on the labels
        A function that modifies the labels based on the experimental 
        design. If `class_func` returns None for a label, then that 
        item is ignored.
       
    vectorizer : sklearn.feature_extraction.DictVectorizer    
       If this is None, then a new `DictVectorizer` is created and
       used to turn the list of dicts created by `phi` into a 
       feature matrix. This happens when we are training.
              
       If this is not None, then it's assumed to be a `DictVectorizer` 
       and used to transform the list of dicts. This happens in 
       assessment, when we take in new instances and need to 
       featurize them as we did in training.
       
    Returns
    -------
    dict
        A dict with keys 'X' (the feature matrix), 'y' (the list of
        labels), 'vectorizer' (the `DictVectorizer`), and 
        'raw_examples' (the example strings, for error analysis).
    """    
    labels = []
    feat_dicts = []
    raw_examples = []
    for paragraph, label in reader():
        cls = class_func(label)
        if cls != None:
            labels.append(cls)
            raw_examples.append(paragraph)
            
            features = Counter()
            for phi in phi_list:
                cur_feats = phi(paragraph)
                # If we won't accidentally blow away data, merge 'em.
                overlap_feature_names = features.viewkeys() & cur_feats.viewkeys()
                if verbose and len(overlap_feature_names) > 0:
                    print "Note: Overlap features are ", overlap_feature_names
                features |= cur_feats
            feat_dicts.append(features)
    
    # In training, we want a new vectorizer, but in 
    # assessment, we featurize using the existing vectorizer:
    feat_matrix = None    
    if vectorizer == None:
        vectorizer = DictVectorizer(sparse=True)
        feat_matrix = vectorizer.fit_transform(feat_dicts)
    else:
        feat_matrix = vectorizer.transform(feat_dicts)
        
    return {'X': feat_matrix, 
            'y': labels, 
            'vectorizer': vectorizer, 
            'raw_examples': raw_examples}

def experiment_features(
        train_reader=data_readers.toy, 
        assess_reader=None, 
        train_size=0.7,
        phi_list=[fe.manual_content_flags], 
        class_func=lt.identity_class_func,
        train_func=training.fit_maxent_with_crossvalidation,
        score_func=utils.safe_weighted_f1,
        verbose=True):
    """Generic experimental framework for hand-crafted features. 
    Either assesses with a random train/test split of `train_reader` 
    or with `assess_reader` if it is given.
    
    Parameters
    ----------
    train_reader : data iterator (default: `train_reader`)
        Iterator for training data.
       
    assess_reader : iterator or None (default: None)
        If None, then the data from `train_reader` are split into 
        a random train/test split, with the the train percentage 
        determined by `train_size`. If not None, then this should 
        be an iterator for assessment data (e.g., `dev_reader`).
        
    train_size : float (default: 0.7)
        If `assess_reader` is None, then this is the percentage of
        `train_reader` devoted to training. If `assess_reader` is
        not None, then this value is ignored.
       
    phi_list : array of feature functions (default: [`manual_content_flags`])
        Any function that takes a string as input and returns a 
        bool/int/float-valued dict as output.
       
    class_func : function on the labels
        A function that modifies the labels based on the experimental 
        design. If `class_func` returns None for a label, then that 
        item is ignored.
       
    train_func : model wrapper (default: `fit_maxent_with_crossvalidation`)
        Any function that takes a feature matrix and a label list
        as its values and returns a fitted model with a `predict`
        function that operates on feature matrices.
    
    score_metric : function name (default: `utils.safe_weighted_f1`)
        This should be an `sklearn.metrics` scoring function. The 
        default is weighted average F1.
        
    verbose : bool (default: True)
        Whether to print out the model assessment to standard output.
       
    Prints
    -------    
    To standard output, if `verbose=True`
        Model confusion matrix and a model precision/recall/F1 report.
        
    Returns
    -------
    float
        The overall scoring metric as determined by `score_metric`.
    
    """        
    # Train dataset:
    train = build_dataset(train_reader, phi_list, class_func, vectorizer=None) 
    
    # Manage the assessment set-up:
    X_train = train['X']
    y_train = train['y']
    X_assess = None 
    y_assess = None
    if assess_reader == None:
         X_train, X_assess, y_train, y_assess = train_test_split(
                X_train, y_train, train_size=train_size)
    else:
        assess = build_dataset(
            assess_reader, 
            phi_list, 
            class_func, 
            vectorizer=train['vectorizer'])
        X_assess, y_assess = assess['X'], assess['y']
        
    # Train:      
    mod = train_func(X_train, y_train)    
    
    # Predictions:
    predictions = mod.predict(X_assess)
    
    # Report:
    if verbose:
        print classification_report(y_assess, predictions, digits=3)
        print confusion_matrix(y_assess, predictions)
        print "Correlation: ", pearsonr(y_assess, predictions)[0]
        print "(Rows are truth; columns are predictions)"
        
    # Return the overall score:
    return score_func(y_assess, predictions)