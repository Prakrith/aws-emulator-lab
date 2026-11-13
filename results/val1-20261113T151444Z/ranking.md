| # | Tier | Service | Sampled pass | Ops implemented | Smoke | Notes |
|---|---|---|---|---|---|---|
| 1 | A | sqs | 40/40 (100%) | 23/23 (100%) | 6/6 |  |
| 2 | A | kms | 37/40 (92%) | 52/54 (96%) | 6/6 | 3 of 40 sampled tests hit 501 |
| 3 | A | sns | 36/40 (90%) | 42/42 (100%) | 5/5 | 3 timed out; 1 target errors |
| 4 | A | stepfunctions | 36/40 (90%) | 37/37 (100%) | 6/6 |  |
| 5 | A | s3 | 36/40 (90%) | 107/112 (96%) | 8/8 | 1 target errors |
| 6 | A | iam | 36/40 (90%) | 158/180 (88%) | 8/8 | 4 of 40 sampled tests hit 501 |
| 7 | A | dynamodb | 34/40 (85%) | 58/58 (100%) | 6/6 | 4 target errors |
| 8 | A | eventbridge | 34/40 (85%) | 57/57 (100%) | 8/8 | 1 timed out |
| 9 | A | secretsmanager | 34/40 (85%) | 23/23 (100%) | 5/5 | 1 timed out; 2 target errors |
| 10 | B | ecr | 33/40 (82%) | 58/58 (100%) | 5/5 | 2 timed out; 1 target errors |
| 11 | B | cloudwatch | 33/40 (82%) | 50/55 (91%) | 5/5 | 1 of 40 sampled tests hit 501; 2 target errors |
| 12 | B | glue | 33/40 (82%) | 200/306 (65%) | 7/7 | 3 of 40 sampled tests hit 501; 1 timed out |
| 13 | B | cloudformation | 32/40 (80%) | 85/90 (94%) | 5/5 | 1 of 40 sampled tests hit 501; 1 target errors |
| 14 | B | kinesis | 30/40 (75%) | 43/45 (96%) | 5/5 | 4 of 40 sampled tests hit 501; 2 target errors |
| 15 | B | sts | 30/40 (75%) | 8/11 (73%) | 5/5 | 1 of 40 sampled tests hit 501; 1 timed out |
| 16 | B | batch | 27/40 (68%) | 47/48 (98%) | 14/14 | 2 timed out; 1 target errors |
| 17 | B | ecs | 26/40 (65%) | 68/88 (77%) | 7/7 | 1 of 40 sampled tests hit 501; 5 timed out; 1 target errors |
| 18 | B | rds | 25/40 (62%) | 119/168 (71%) | 4/4 | 6 of 40 sampled tests hit 501; 4 timed out; 1 target errors |
| 19 | B | apigateway | 24/40 (60%) | 123/124 (99%) | 5/5 | 2 of 40 sampled tests hit 501; 2 target errors |
| 20 | B | lambda | 24/40 (60%) | 83/88 (94%) | 5/5 | 6 target errors |
| 21 | C | sagemaker | 29/39 (74%) | 178/409 (44%) | 4/4 | 2 of 39 sampled tests hit 501; 4 target errors |
| 22 | C | ssm | 14/40 (35%) | 64/152 (42%) | 4/4 | 13 of 40 sampled tests hit 501; 3 timed out; 5 target errors |
| 23 | C | ec2 | 12/40 (30%) | 541/807 (67%) | 4/4 | 15 of 40 sampled tests hit 501; 3 timed out |
| 24 | C | vpc | 12/40 (30%) | 541/807 (67%) | 9/9 | 15 of 40 sampled tests hit 501; 3 timed out |
| 25 | C | athena | 12/40 (30%) | 27/70 (39%) | 5/6 | 17 of 40 sampled tests hit 501; 1 timed out; 1 target errors |
