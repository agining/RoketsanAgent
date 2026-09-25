from data_loader import (
    load_reports,
    load_zones,
)

from reports import (
    parse_reports,
)


def main():

    reports = load_reports()
    zones_data = load_zones()

    parsed_reports = parse_reports(
        reports,
        zones_data,
    )

    print()
    print("İlk parse edilen raporlar:")
    print()

    for report in parsed_reports[:20]:

        print(
            "--------------------------------"
        )

        print(
            "Time:",
            report["time"]
        )

        print(
            "Source:",
            report["source"]
        )

        print(
            "Text:",
            report["text"]
        )

        print(
            "Type:",
            report["report_type"]
        )

        print(
            "Coord:",
            report["coord"]
        )

        print(
            "Vehicle:",
            report["vehicle_type"]
        )

        print(
            "Count:",
            report["count"]
        )

        print(
            "Zone:",
            report["zone"]
        )

        print(
            "Stationary:",
            report["claims_stationary"]
        )

        print(
            "Moving:",
            report["claims_moving"]
        )

        print(
            "Fast:",
            report["claims_fast"]
        )

        print(
            "Leaving:",
            report["claims_leaving"]
        )

        print(
            "Approaching:",
            report["claims_approaching"]
        )

        print(
            "Normal:",
            report["claims_normal"]
        )

        print(
            "Friendly:",
            report["friendly_claim"]
        )

        print(
            "Exercise:",
            report["exercise_claim"]
        )


if __name__ == "__main__":
    main()