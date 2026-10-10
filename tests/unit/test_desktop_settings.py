from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_to_pdf import desktop_launcher as desktop
from dwg_to_pdf.cad.selection import CadCandidate


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'user settings'))
    candidate = CadCandidate('autocad', 'AutoCAD.Application.24', 'id', tmp_path / 'acad.exe', 'AutoCAD', '24.0')
    monkeypatch.setattr(desktop, 'discover_candidates', lambda provider: (candidate,))
    pc3 = tmp_path / 'DWG To PDF.pc3'
    pc3.write_bytes(b'validated plotter')
    config = tmp_path / '설정 (현재 PC).toml'
    config.write_text('''[cad]
provider="autocad"
prog_id="AutoCAD.Application.24"
allow_experimental_autocad=true
[matching]
auto_match_enabled=true
matching_threshold=1.0
minimum_score_gap=1.0
[plot]
plotter_name="DWG To PDF.pc3"
media_width_mm=297.0
media_height_mm=210.0
style_sheet="monochrome.ctb"
autocad_pc3_path=''' + json.dumps(pc3.as_posix(), ensure_ascii=False) + '\n', encoding='utf-8')
    prompts=[]
    results=[]
    selected=SimpleNamespace(
        choose_source_mode=lambda:'folder', choose_input_folder=lambda:'C:/input',
        choose_output_folder=lambda:'C:/output', choose_cad_provider=lambda:'autocad',
        confirm_experimental_autocad=lambda:True, choose_cad_candidate=lambda candidates:candidates[0].prog_id,
        choose_autocad_config=lambda:prompts.append(True) or str(config),
        show_result=results.append, close=lambda:None)
    cache=tmp_path / 'user settings/DWG-to-PDF/autocad-settings.json'
    return candidate, config, pc3, selected, prompts, results, cache


def test_successful_config_is_automatically_reused_without_picker(setup):
    candidate, config, _, selected, prompts, _, cache = setup
    calls=[]
    assert desktop.run_desktop(lambda args:calls.append(args) or 0,ui=selected)==0
    assert cache.is_file()
    original_mtime = cache.stat().st_mtime_ns
    selected.choose_autocad_config=lambda:pytest.fail('Validated setting must apply automatically')
    assert desktop.run_desktop(lambda args:calls.append(args) or 0,ui=selected)==0
    assert prompts==[True]
    assert calls[0]==calls[1]
    assert calls[1][-2:]==['--config',str(config)]
    assert cache.stat().st_mtime_ns == original_mtime


def test_single_installation_uses_saved_config_without_extra_confirmation(setup):
    candidate, config, _, selected, _, results, _ = setup
    desktop.remember_autocad_config(candidate, str(config), desktop.autocad_config_snapshot(str(config)))
    selected.confirm_experimental_autocad = lambda: pytest.fail('No experimental confirmation')
    selected.choose_cad_candidate = lambda _: pytest.fail('Single installation is automatic')
    selected.choose_autocad_config = lambda: pytest.fail('Saved valid config is automatic')
    calls = []
    assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=selected) == 0
    assert calls[0][-2:] == ['--config', str(config)]
    assert results == [0]


def test_multiple_installations_use_only_uniquely_valid_saved_config(setup, monkeypatch):
    candidate, config, _, selected, _, _, _ = setup
    other = replace(candidate, prog_id='AutoCAD.Application.25', clsid='other', executable=Path('C:/other/acad.exe'))
    desktop.remember_autocad_config(candidate, str(config), desktop.autocad_config_snapshot(str(config)))
    monkeypatch.setattr(desktop, 'discover_candidates', lambda _: (other, candidate))
    selected.choose_cad_candidate = lambda _: pytest.fail('One validated installation is automatic')
    selected.choose_autocad_config = lambda: pytest.fail('Use validated saved config')
    calls = []
    assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=selected) == 0
    assert calls[0][calls[0].index('--cad-prog-id') + 1] == 'AutoCAD.Application.24'


@pytest.mark.parametrize('other_installation', [False, True])
def test_saved_generic_alias_is_reused_per_installation(setup, monkeypatch, other_installation):
    candidate, config, _, selected, _, _, _ = setup
    alias = replace(candidate, prog_id='AutoCAD.Application')
    desktop.remember_autocad_config(alias, str(config), desktop.autocad_config_snapshot(str(config)))
    candidates = (candidate, alias)
    if other_installation:
        candidates += (replace(candidate, prog_id='AutoCAD.Application.25', clsid='other', executable=Path('C:/other/acad.exe')),)
    monkeypatch.setattr(desktop, 'discover_candidates', lambda _: candidates)
    selected.choose_cad_candidate = lambda _: pytest.fail('Only one installation has valid settings')
    selected.choose_autocad_config = lambda: pytest.fail('Generic alias cache must be reused')
    calls = []
    assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=selected) == 0
    assert calls[0][calls[0].index('--cad-prog-id') + 1] == 'AutoCAD.Application'
    assert calls[0][-2:] == ['--config', str(config)]


@pytest.mark.parametrize('saved_count', [0, 2])
def test_ambiguous_installations_remain_cancellable(setup, monkeypatch, saved_count):
    candidate, config, _, selected, _, results, _ = setup
    other = replace(candidate, prog_id='AutoCAD.Application.25', clsid='other', executable=Path('C:/other/acad.exe'))
    candidates = (candidate, other)
    for item in candidates[:saved_count]:
        desktop.remember_autocad_config(item, str(config), desktop.autocad_config_snapshot(str(config)))
    monkeypatch.setattr(desktop, 'discover_candidates', lambda _: candidates)
    prompts = []
    selected.choose_cad_candidate = lambda items: prompts.append(items) or None
    assert desktop.run_desktop(lambda _: pytest.fail('Cancelled selection must not start'), ui=selected) == 0
    assert len(prompts) == 1
    assert {item.prog_id for item in prompts[0]} == {'AutoCAD.Application.24', 'AutoCAD.Application.25'}
    assert results == []


@pytest.mark.parametrize('code',[1,2])
def test_unsuccessful_conversion_does_not_remember_new_config(setup,code):
    _,_,_,selected,prompts,_,cache=setup
    assert desktop.run_desktop(lambda _:code,ui=selected)==code
    assert not cache.exists()
    assert desktop.run_desktop(lambda _:0,ui=selected)==0
    assert prompts==[True,True]


@pytest.mark.parametrize('change',['config_changed','config_deleted','pc3_changed','pc3_deleted','installation_changed','version_changed','cache_corrupt','cache_schema'])
def test_changed_or_invalid_cached_setting_requests_selection(setup,monkeypatch,change):
    candidate,config,pc3,selected,prompts,_,cache=setup
    assert desktop.run_desktop(lambda _:0,ui=selected)==0
    assert cache.is_file()
    if change=='config_changed':config.write_text('bad[',encoding='utf-8')
    elif change=='config_deleted':config.unlink()
    elif change=='pc3_changed':pc3.write_bytes(b'changed plotter')
    elif change=='pc3_deleted':pc3.unlink()
    elif change=='installation_changed':
        monkeypatch.setattr(desktop,'discover_candidates',lambda _: (replace(candidate,clsid='new-id'),))
    elif change=='version_changed':
        monkeypatch.setattr(desktop,'discover_candidates',lambda _: (replace(candidate,reported_version='24.1'),))
    elif change=='cache_corrupt':cache.write_text('bad{',encoding='utf-8')
    else:cache.write_text('{"version":1,"installations":[]}',encoding='utf-8')
    selected.choose_autocad_config=lambda:prompts.append(True) or ''
    assert desktop.run_desktop(lambda _:pytest.fail('Cancellation must not start CAD'),ui=selected)==0
    assert prompts==[True,True]


def test_cancelled_config_is_not_remembered(setup):
    _,_,_,selected,_,_,cache=setup
    selected.choose_autocad_config=lambda:''
    assert desktop.run_desktop(lambda _:pytest.fail('must not run'),ui=selected)==0
    assert not cache.exists()


@pytest.mark.parametrize('changed_file',['toml','pc3'])
def test_config_changed_during_conversion_is_not_remembered(setup,changed_file):
    _,config,pc3,selected,prompts,results,cache=setup
    def convert(_):
        if changed_file=='toml':
            config.write_text(config.read_text(encoding='utf-8')+'\n# edited during conversion\n',encoding='utf-8')
        else:pc3.write_bytes(b'different plotter during conversion')
        return 0
    assert desktop.run_desktop(convert,ui=selected)==0
    assert results==[0]
    assert not cache.exists()
    assert desktop.run_desktop(lambda _:0,ui=selected)==0
    assert prompts==[True,True]


def test_unwritable_cache_does_not_turn_success_into_conversion_failure(setup,capsys):
    _,_,_,selected,_,results,cache=setup
    cache.parent.parent.parent.mkdir(exist_ok=True)
    cache.parent.parent.write_text('blocked directory',encoding='utf-8')
    assert desktop.run_desktop(lambda _:0,ui=selected)==0
    assert results==[0]
    assert '다음 실행' in capsys.readouterr().err
