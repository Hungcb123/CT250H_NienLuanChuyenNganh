"""Preserve LightGBM's double-threshold decisions on float32 feature inputs."""
import numpy as np
import onnxmltools
from onnx import helper
from onnxmltools.convert.common.data_types import FloatTensorType


def convert_lightgbm_float32(model, feature_count):
    booster=model.booster_ if hasattr(model,'booster_') else model
    converted=onnxmltools.convert_lightgbm(model,initial_types=[('input',FloatTensorType([None,feature_count]))],
                                          target_opset=15,zipmap=False)
    ensemble=next(n for n in converted.graph.node if n.op_type in ['TreeEnsembleClassifier','TreeEnsembleRegressor'])
    attrs={a.name:helper.get_attribute_value(a) for a in ensemble.attribute}
    positions={(t,n):i for i,(t,n) in enumerate(zip(attrs['nodes_treeids'],attrs['nodes_nodeids']))}
    values=list(attrs['nodes_values'])

    def visit(node,tree_id,node_id):
        if 'split_feature' not in node:return
        if node['decision_type']!='<=' or isinstance(node['threshold'],str):
            raise ValueError('Only numeric <= LightGBM splits are supported')
        i=positions[tree_id,node_id]
        if attrs['nodes_featureids'][i]!=node['split_feature'] or attrs['nodes_modes'][i]!=b'BRANCH_LEQ':
            raise ValueError('Converter changed numeric tree topology')
        threshold=node['threshold'];rounded=np.float32(threshold)
        if float(rounded)>threshold:
            rounded=np.nextafter(rounded,np.float32(-np.inf))
        values[i]=float(rounded)
        visit(node['left_child'],tree_id,attrs['nodes_truenodeids'][i])
        visit(node['right_child'],tree_id,attrs['nodes_falsenodeids'][i])

    for tree_id,tree in enumerate(booster.dump_model()['tree_info']):
        visit(tree['tree_structure'],tree_id,0)
    for a in ensemble.attribute:
        if a.name=='nodes_values':a.CopyFrom(helper.make_attribute('nodes_values',values))
    return converted
