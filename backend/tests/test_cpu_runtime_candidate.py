import pytest
from tools.prepare_cpu_runtime_candidate import validate_distribution, select_wheel


def record():
    return dict(url='https://files.pythonhosted.org/example-1.0-py3-none-any.whl',filename='example-1.0-py3-none-any.whl',bytes=1024,sha256='a'*64)


@pytest.mark.parametrize('change',[dict(url='https://unknown.example/example-1.0-py3-none-any.whl'),dict(filename='../example.whl'),dict(sha256='a'*63),dict(bytes=0)])
def test_unknown_or_invalid_distribution_is_rejected(change):
    item=record();item.update(change)
    with pytest.raises(ValueError):validate_distribution(item)


def test_target_python_wheel_selection_rejects_wrong_platform_or_version():
    def file(name):return dict(filename=name,packagetype='bdist_wheel',yanked=False)
    info=dict(info=dict(requires_python='>=3.10'),urls=[file('example-1.0-cp310-cp310-win_amd64.whl'),file('example-1.0-cp311-cp311-win_amd64.whl')])
    assert select_wheel(info)['filename']=='example-1.0-cp311-cp311-win_amd64.whl'
    info['info']['requires_python']='>=3.12'
    with pytest.raises(ValueError,match='excludes'):select_wheel(info)
