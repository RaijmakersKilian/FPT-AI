def get_report_by_run_id(run_id: str):
    return {
        "run_id": run_id,
        "overall_progress": 80,
        "completed_elements": 120,
        "partial_elements": 20,
        "remaining_elements": 40,
        "element_type_progress": [
            {
                "element_type": "beam",
                "completed_percent": 75
            },
            {
                "element_type": "column",
                "completed_percent": 90
            },
            {
                "element_type": "slab",
                "completed_percent": 65
            }
        ]
    }