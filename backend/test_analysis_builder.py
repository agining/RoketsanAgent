import json

from data_loader import (
    load_zones,
)

from analysis_builder import (
    build_analysis,
    save_analysis,
)


def main():

    # --------------------------------
    # TRACK FEATURES
    # --------------------------------

    with open(
        "track_features_output.json",
        "r",
        encoding="utf-8",
    ) as f:

        track_data = json.load(
            f
        )

    # --------------------------------
    # LLM RISK
    # --------------------------------

    with open(
        "llm_track_risk_results.json",
        "r",
        encoding="utf-8",
    ) as f:

        risk_results = json.load(
            f
        )

    # --------------------------------
    # ZONES
    # --------------------------------

    zones_data = load_zones()

    # --------------------------------
    # FINAL ANALYSIS
    # --------------------------------

    analysis = build_analysis(
        zones_data=
            zones_data,

        track_data=
            track_data,

        risk_results=
            risk_results,
    )

    save_analysis(
        analysis,
        output_path="analysis.json",
    )

    print(
        "analysis.json oluşturuldu."
    )

    print()

    print(
        json.dumps(
            analysis[
                "operation_summary"
            ],
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()