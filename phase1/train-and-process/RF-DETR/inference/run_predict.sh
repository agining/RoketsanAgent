#!/usr/bin/env bash
cd /home/ubuntu/vol/RoketDetect/RFDETR
while ps -eo args | grep -q '^python train_rfdetr.py'; do sleep 3; done
sleep 3
echo "$(date -u +%T) training finished"; ls -la outputs/rfdetr_large_960_ep26_plus1_trainval | grep -E "pth|ckpt"
for i in 0 1 2; do .venv/bin/python predict_test_sahi.py --weights outputs/rfdetr_large_960_ep26_plus1_trainval/checkpoint_best_ema.pth --shard $i --num-shards 3 --out submissions/rfdetr960_trainval_sahi960_agnms_conf050_part$i.csv > submissions/predict_part$i.log 2>&1 & done
wait
tail -n1 submissions/predict_part*.log
.venv/bin/python merge_submission_shards.py --out submissions/rfdetr960_trainval_sahi960_agnms_conf050.csv submissions/rfdetr960_trainval_sahi960_agnms_conf050_part0.csv submissions/rfdetr960_trainval_sahi960_agnms_conf050_part1.csv submissions/rfdetr960_trainval_sahi960_agnms_conf050_part2.csv
echo "$(date -u +%T) done"
