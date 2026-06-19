from pathlib import Path

from text_to_gds.paper_benchmarks import run_paper_benchmark_suite


ROOT = Path(__file__).resolve().parents[1]


def test_paper_reproduction_suite(tmp_path, capsys):
    suite = run_paper_benchmark_suite(
        ROOT / "benchmarks" / "papers",
        report_path=tmp_path / "paper-benchmarks.json",
    )
    for result in suite["results"]:
        print(f"{result['paper_id']}: {result['status'].upper()}")
    output = capsys.readouterr().out
    assert "Planat_2020: PASSED" in output
    assert "Gaydamachenko_2022: PASSED" in output
    assert suite["counts"]["failed"] == 0
