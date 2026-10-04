import importlib.util
from pathlib import Path
import pytest

path=Path(__file__).resolve().parents[2]/'tools'/'regression'/'gstarcad'/'test_gstar_regression.py'
spec=importlib.util.spec_from_file_location('handoff',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_native_success_preserves_result_and_records():
    value=object();events=[]
    observed=module.observe_extraction(lambda *a,**kw:value,events)
    assert observed(1,x=2) is value
    assert events==['native_success']

def test_unavailable_is_recorded_and_reraised_for_original_fallback():
    events=[];failure=module.NativeExtractionUnavailable('untrusted')
    def original():raise failure
    with pytest.raises(module.NativeExtractionUnavailable) as caught:
        module.observe_extraction(original,events)()
    assert caught.value is failure
    assert events==['native_unavailable_COM_fallback']

def test_permanent_error_is_not_reported_as_fallback_or_success():
    events=[];failure=RuntimeError('permanent')
    def original():raise failure
    with pytest.raises(RuntimeError) as caught:module.observe_extraction(original,events)()
    assert caught.value is failure and events==[]
