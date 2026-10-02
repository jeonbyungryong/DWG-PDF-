import importlib.util
from pathlib import Path


def comparison():
    path = Path(__file__).parents[2] / "tools" / "compare_benchmark_results.py"
    spec = importlib.util.spec_from_file_location("comparison", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frame(x=1.0, rotation=0):
    return {"scale": {"numerator": "1", "denominator": "1"},
            "rotation": rotation,
            "plot_window": {"lower_left": {"x": x, "y": 2.0},
                            "upper_right": {"x": 421.0, "y": 299.0}}}


def test_decision_comparison_tolerates_serialization_noise_but_not_window_drift():
    module = comparison()
    assert hasattr(module, "same_decision"), "numeric decision comparator is missing"
    assert module.same_decision(frame(), frame(1 + 1e-14))
    assert not module.same_decision(frame(), frame(1 + 1e-6))
    assert not module.same_decision(frame(), frame(rotation=90))
