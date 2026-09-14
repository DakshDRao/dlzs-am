"""Create the fixed 100-passage corpus used by the attention ranking study.

The corpus is deliberately self-contained: it uses deterministic, hand-written
topic and condition templates, so the exact text can be checked into the
repository and regenerated without a dataset download or a random seed.

Run from the repository root, for example:
  python src/make_attention_corpus.py --output src/attention_corpus_100.json
"""

import argparse
import json
from pathlib import Path


VARIANTS = [
    {
        "time": "before sunrise",
        "condition": "a short power interruption changed the first readings",
        "response": "the team repeated the affected measurements after the instruments restarted",
        "conclusion": "the final decision used both the original and repeated observations",
    },
    {
        "time": "during a busy afternoon",
        "condition": "several observations arrived later than expected",
        "response": "the analysts kept the timestamps and compared late and early records separately",
        "conclusion": "the report treated timing as a possible source of variation",
    },
    {
        "time": "after two days of heavy rain",
        "condition": "nearby activity produced a second change in the measurements",
        "response": "the investigators added a control location before interpreting the trend",
        "conclusion": "the result was reported only when the control supported the same direction",
    },
    {
        "time": "on a clear weekend morning",
        "condition": "one sensor or record contained an unusual outlier",
        "response": "the team checked the raw value and calibration history instead of deleting it",
        "conclusion": "the outlier remained visible in the appendix and was excluded only from the mean",
    },
    {
        "time": "near the end of a month-long trial",
        "condition": "the system became more variable as demand increased",
        "response": "the engineers grouped the results by load and tested the busiest interval again",
        "conclusion": "the recommendation included a limit for the high-demand case",
    },
]


TOPICS = [
    {
        "name": "railway scheduling",
        "lead": "At a regional railway station, dispatchers reviewed the departure board and platform queue",
        "object": "train movements",
        "measure": "departure times and passenger counts",
        "action": "They compared the records with the timetable and marked every platform change",
    },
    {
        "name": "greenhouse sensors",
        "lead": "In a university greenhouse, engineers checked a network of temperature and humidity sensors",
        "object": "sensor readings",
        "measure": "temperature, humidity, and response delay",
        "action": "They compared each node with a calibrated reference instrument and recorded its location",
    },
    {
        "name": "library lending",
        "lead": "At a city library, staff reviewed a program that lent gardening tools beside books",
        "object": "borrowed equipment",
        "measure": "requests, repairs, and return times",
        "action": "They matched the lending log with volunteer repair notes and school calendar dates",
    },
    {
        "name": "coastal sampling",
        "lead": "During a coastal survey, researchers visited a river mouth and a sheltered bay",
        "object": "water samples",
        "measure": "salinity, suspended material, and sampling time",
        "action": "They compared the sites while recording rainfall, tides, and instrument calibration",
    },
    {
        "name": "clinic appointments",
        "lead": "At a community clinic, coordinators studied the schedule for routine diagnostic appointments",
        "object": "patient visits",
        "measure": "waiting time, arrival pattern, and appointment length",
        "action": "They matched the schedule with anonymized check-in records and staffing levels",
    },
    {
        "name": "software deployment",
        "lead": "A software team reviewed a staged deployment of a service used by several internal groups",
        "object": "service requests",
        "measure": "latency, error rate, and release stage",
        "action": "They compared application logs with the deployment timeline and rollback notes",
    },
    {
        "name": "farm irrigation",
        "lead": "On a mixed-crop farm, agronomists inspected an irrigation schedule across several fields",
        "object": "soil readings",
        "measure": "moisture, pump runtime, and plant growth",
        "action": "They compared field sensors with manual samples and recorded the weather between visits",
    },
    {
        "name": "bus reliability",
        "lead": "A transport office examined bus journeys on three routes connecting outer neighborhoods",
        "object": "vehicle journeys",
        "measure": "arrival delay, passenger load, and route segment",
        "action": "They compared ticket records with location traces and noted road works on each route",
    },
    {
        "name": "water treatment",
        "lead": "At a municipal water plant, operators checked the stages used to treat incoming river water",
        "object": "treatment batches",
        "measure": "turbidity, chemical dose, and settling time",
        "action": "They compared laboratory samples with process logs and reviewed the valve settings",
    },
    {
        "name": "astronomy observations",
        "lead": "At a small observatory, astronomers reviewed a sequence of images of a variable star",
        "object": "image frames",
        "measure": "brightness, exposure time, and sky condition",
        "action": "They compared the frames with a reference star and retained the weather notes",
    },
    {
        "name": "school attendance",
        "lead": "A secondary school team studied attendance across classes using a new morning check-in process",
        "object": "attendance records",
        "measure": "arrival time, absence reason, and class size",
        "action": "They compared the electronic register with teacher notes and the transport timetable",
    },
    {
        "name": "factory inspection",
        "lead": "In a small factory, quality engineers inspected a line producing precision metal brackets",
        "object": "finished parts",
        "measure": "dimension, surface score, and machine setting",
        "action": "They compared sampled parts with the inspection standard and logged each tool change",
    },
    {
        "name": "solar generation",
        "lead": "An energy cooperative reviewed output from rooftop solar arrays installed on several buildings",
        "object": "power intervals",
        "measure": "generated energy, cloud cover, and inverter temperature",
        "action": "They compared meter readings with the weather station and marked maintenance periods",
    },
    {
        "name": "forest survey",
        "lead": "Ecologists surveyed a forest reserve after installing plots along a stream and a ridge",
        "object": "field observations",
        "measure": "species count, soil moisture, and plot location",
        "action": "They compared repeated visits and recorded trail use near every plot",
    },
    {
        "name": "archaeology dig",
        "lead": "At an archaeology site, researchers catalogued finds from adjacent layers of a test trench",
        "object": "recorded artefacts",
        "measure": "depth, material, and grid position",
        "action": "They compared field sketches with the database and retained uncertain classifications",
    },
    {
        "name": "public health survey",
        "lead": "A public health group reviewed responses from households invited to a local wellness survey",
        "object": "survey responses",
        "measure": "response rate, age band, and collection method",
        "action": "They compared online and paper forms and documented every change to the questionnaire",
    },
    {
        "name": "music rehearsal",
        "lead": "A community orchestra evaluated a rehearsal plan for a concert with several new sections",
        "object": "rehearsal passages",
        "measure": "tempo, missed entries, and section balance",
        "action": "They compared conductor notes with recordings and marked passages needing another rehearsal",
    },
    {
        "name": "urban traffic",
        "lead": "City planners examined traffic at four intersections before changing signal timings",
        "object": "vehicle flows",
        "measure": "queue length, crossing time, and turning movement",
        "action": "They compared camera counts with signal logs and noted nearby construction activity",
    },
    {
        "name": "network security",
        "lead": "A security team reviewed alerts from a business network after deploying a new detection rule",
        "object": "security events",
        "measure": "alert type, response time, and source segment",
        "action": "They compared alerts with authenticated activity and preserved the original event order",
    },
    {
        "name": "battery materials",
        "lead": "Materials researchers tested small battery cells made with several electrode formulations",
        "object": "cell cycles",
        "measure": "capacity, temperature, and cycle count",
        "action": "They compared each cell with a control formulation and recorded the charging profile",
    },
]


def build_corpus():
    texts = []
    for topic_index, topic in enumerate(TOPICS):
        for variant_index, variant in enumerate(VARIANTS):
            text = (
                f"{topic['lead']} {variant['time']}. "
                f"The review focused on {topic['object']}: {topic['measure']}. "
                f"{topic['action']}. "
                f"In that period, {variant['condition']}. "
                f"{variant['response']}. "
                f"{variant['conclusion']}."
            )
            texts.append(text)
    assert len(texts) == 100
    return texts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent / "attention_corpus_100.json")
    args = parser.parse_args()
    texts = build_corpus()
    payload = {
        "format": "dlzs_attention_corpus_v1",
        "count": len(texts),
        "description": "100 deterministic passages from 20 technical and public-service topics, five conditions each.",
        "construction": "Cartesian product of the fixed TOPICS and VARIANTS tables in make_attention_corpus.py; no random sampling.",
        "texts": texts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(texts)} passages to {args.output.resolve()}")


if __name__ == "__main__":
    main()
