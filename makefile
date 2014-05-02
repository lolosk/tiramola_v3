default:
	tiramola auto_pilot minutes=1001
	#doing nothing
sync:
	rsync -av * torchestrator:~/bin/tiramola
clean:
	tiramola kill_nodes
	tiramola kill_workload 
	tiramola bootstrap_cluster used=8
	tiramola load_data records=10000000
clean_quick:
	tiramola kill_nodes
	tiramola kill_workload 
	tiramola bootstrap_cluster used=8
	tiramola load_data records=10000
	rm files/logs/measurements.txt &>/dev/null
train:
	rm files/logs/measurements.txt
	tiramola train

experiment1:
	tiramola experiment target=8000 offset=6000 period=60 time=180
experiment2:
	#6 hours
	tiramola experiment target=8000 offset=6000 period=120 time=360
