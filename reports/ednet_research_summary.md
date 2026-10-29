# ERA: EdNet Behavioral Feature Analysis

**Profiles analyzed:** 100

## Method

Behavioral features were extracted from EdNet-KT2 event logs. Numeric features are summarized using count, mean, median, minimum, and maximum. Pearson correlations are descriptive associations only.

## Descriptive statistics

| Feature | Count | Mean | Median | Minimum | Maximum |
|---|---:|---:|---:|---:|---:|
| event_count | 100 | 1815.38 | 438.5 | 3.0 | 32319.0 |
| enter_events | 100 | 539.88 | 131.0 | 1.0 | 8788.0 |
| respond_events | 100 | 735.62 | 162.5 | 1.0 | 14743.0 |
| submit_events | 100 | 539.88 | 131.0 | 1.0 | 8788.0 |
| unique_response_items | 100 | 502.63 | 135.0 | 1.0 | 8091.0 |
| answer_revisions | 100 | 182.61 | 27.5 | 0.0 | 4899.0 |
| session_count_30min_gap | 100 | 41.56 | 10.5 | 1.0 | 460.0 |
| observed_span_seconds | 100 | 5777207.351 | 2346305.339 | 79.656 | 34045957.01 |
| total_session_seconds | 100 | 52682.224 | 10777.396 | 79.656 | 784551.981 |
| median_session_seconds | 100 | 835.728 | 611.044 | 53.294 | 5092.373 |
| median_inter_event_seconds | 100 | 11.565 | 10.557 | 0.593 | 52.145 |
| median_session_gap_seconds | 100 | 180884.928 | 64187.649 | 0.0 | 4035619.311 |

## Exploratory correlations

| Feature pair | Pearson correlation |
|---|---:|
| event_count vs answer_revisions | 0.9495 |
| event_count vs unique_response_items | 0.9905 |
| session_count_30min_gap vs total_session_seconds | 0.8089 |
| median_inter_event_seconds vs answer_revisions | -0.0227 |

## Event source counts

| Source | Events across analyzed profiles |
|---|---:|
| adaptive_offer | 9740 |
| diagnosis | 2270 |
| my_note | 22223 |
| review | 886 |
| review_quiz | 6448 |
| sprint | 139079 |
| tutor | 892 |

## Interpretation and limitations

- These results describe recorded activity in the analyzed subset.
- Event counts and response revisions can reflect different usage patterns; they are not direct measures of ability, effort, or intelligence.
- Session boundaries depend on the chosen 30-minute inactivity heuristic.
- EdNet-KT2 contains TOEIC-learning activity, not JEE Advanced responses. Its behavioral patterns must not be presented as validated JEE predictors.
- ERA may use this analysis to motivate hypotheses for adaptive assessment, but any transfer to JEE requires validation on relevant data.

## Reproducibility

Input: `data/ednet_behavior_features.csv`
Machine-readable output: `reports/ednet_research_summary.json`
