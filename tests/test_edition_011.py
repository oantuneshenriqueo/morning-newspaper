"""Fixes from the debug report of edition No. 011 (2026-11-21). No test touches the network."""
import importlib.util

import pytest

from conftest import SCRIPTS, SKILL


@pytest.fixture
def assemble_module():
    spec = importlib.util.spec_from_file_location("assemble_mod_011", SCRIPTS / "assemble.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ok(proc):
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc


# 1. printed? missed "IA" vs "inteligência artificial" and "segurança" vs "cibersegurança".

def test_ai_told_with_another_name_is_printed_before(collect_module):
    past = ["Alibaba lança novo modelo de inteligência artificial com reforço da cibersegurança"]
    assert collect_module.printed_before(
        "Gigante chinesa apresenta um novo modelo de IA de topo, com reforço na segurança", past)


def test_ai_aliases_fold_into_one_token(collect_module):
    s = collect_module.stems
    assert s("Novo modelo de IA") & s("novo modelo de inteligência artificial") >= {"iaxxx"}
    assert "iaxxx" in s("Google ships a new AI model") & s("Artificial intelligence model from Google")
    assert "segur" in s("Curso de cibersegurança") and "attac" in s("Cyberattack hits a bank")


def test_lowercase_ia_is_the_verb_not_ai(collect_module):
    assert "iaxxx" not in collect_module.stems("Ele ia ao mercado quando o temporal começou")
    # An all-caps title says nothing about which words are abbreviations.
    assert "iaxxx" not in collect_module.stems("ELE IA AO MERCADO QUANDO CHOVEU")


def test_short_ciber_word_is_left_alone(collect_module):
    # Only a prefix followed by a real word is cut ("ciberataque" → "ataque").
    assert "ciber" in collect_module.stems("Polícia fecha ciber café")


# 3. The day and month a story came out are not "numbers not in the source".

def test_publication_date_backs_day_and_month(assemble_module):
    src = "Especialistas pedem correção imediata de falhas no NGINX SpaceMoney"
    text = ["Especialistas pediram a correção de falhas no NGINX, segundo a SpaceMoney, na sexta-feira, 20 de novembro."]
    before = assemble_module.unsupported(text, src, True)
    assert any("numbers not in the source: 20" in n for n in before)
    after = assemble_module.unsupported(text, src + " " + assemble_module.date_words("2026-11-20 10:45"), True)
    assert not any("numbers" in n for n in after)
    assert not any("novembro" in n for n in after)


def test_date_words_leave_the_hour_out(assemble_module):
    words = assemble_module.date_words("2026-11-20 10:45").split()
    assert "20" in words and "novembro" in words and "November" in words
    assert "10" not in words and "45" not in words
    assert assemble_module.date_words("") == "" and assemble_module.date_words("soon") == ""


def test_headline_date_check_cleared_in_a_real_run(assembler, collected):
    first = next(n for lst in collected["news"].values() for n in lst if n["id"] == "a1")
    day = int(first["date"][8:10])
    assembler.edition["headline"]["text"] += f" It came out on the {day}th."
    proc = ok(assembler.run())
    assert f"numbers not in the source: {day}" not in proc.stdout


# 5. A plural attribution for a story only one outlet carries.

def test_plural_attribution_with_one_outlet_is_checked(assemble_module):
    refs = {"a1": {"id": "a1", "outlet": "Pplware", "title": "Gigante chinesa apresenta modelo"}}
    note = assemble_module.overstated_attribution(["Sites relatam que uma gigante chinesa apresentou um modelo."],
                                                  refs["a1"], refs)
    assert note and "Pplware" in note
    assert assemble_module.overstated_attribution(["Segundo o Pplware, uma gigante apresentou um modelo."],
                                                  refs["a1"], refs) is None


def test_plural_attribution_is_fine_when_several_outlets_carry_it(assemble_module):
    refs = {"a1": {"id": "a1", "outlet": "Pplware", "title": "x"},
            "a4": {"id": "a4", "outlet": "Tek Sapo", "title": "y", "same_as": "a1"}}
    for ref in ("a1", "a4"):
        assert assemble_module.overstated_attribution(["Sites relatam o lançamento."], refs[ref], refs) is None


def test_plural_attribution_check_in_a_real_run(assembler):
    sid, lst = next(iter(assembler.edition["sections"].items()))
    lst[0]["text"] = "Outlets report that it beats larger models on the test."
    proc = ok(assembler.run())
    assert "plural attribution" in proc.stdout


# 4. The final check comes before publishing.

def test_next_steps_check_before_publishing(assembler):
    out = ok(assembler.run()).stdout
    assert out.index("6. Check every sentence") < out.index("7. Then publish exactly")
    assert "republish" not in out


def test_skill_orders_check_before_publish():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert text.index("### 6. Final check") < text.index("### 7. Publish to the newsstand") < text.index("### 8. Deliver")
    assert "6. Check every sentence against its source" in text
