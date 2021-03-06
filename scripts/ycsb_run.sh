#!/bin/sh
#########  YCSB WORKLOAD PARAMS  ########
threads=150

killall java

echo "
recordcount=10000
workload=com.yahoo.ycsb.workloads.CoreWorkload
sinusoidal=false
readallfields=true
readproportion=1
updateproportion=0
scanproportion=0
insertproportion=0
requestdistribution=uniform
hostsFile=/opt/hosts
maxexecutiontime=1000000000
" > my_workload

ycsb run cassandra-cql -P my_workload -threads $threads  -s &> /root/ycsb_run.log &
