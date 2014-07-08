__author__ = 'cmantas'
from time import sleep
import CassandraCluster as Servers
import ClientsCluster as Clients
from lib.persistance_module import env_vars
from Monitoring import MonitorVms
from new_decision_module import RLDecisionMaker as DM
from lib.tiramola_logging import get_logger
from time import time
from os import remove
from threading import Thread

#######  STATIC VARS  ###############
my_logger = get_logger('COORDINATOR', 'INFO', logfile='files/logs/Coordinator.log')
my_logger.debug("--------- NEW RUN  -----------------")
#the (pending) decision at the present moment
decision = None
running_process=None
#get the endpoint for the monitoring system
monitoring_endpoint = Clients.get_monitoring_endpoint()
monVms = MonitorVms(monitoring_endpoint)

error = None

#check if cluster exists
if Servers.exists():
    my_logger.info( "Cluster exists using it as is")
    #make sure no workload is running
else:
    my_logger.error("Create the cluster first and then run the coordinator")
    exit(-1)


def implement_decision():
    """
    Used to asynchronously implement the decision that has been updated  by the run function
    """
    global decision
    action = decision["action"]
    count = decision['count']

    try:
        if action == "ADD":
            decision_module.pending_action = action
            my_logger.info("Will add %d nodes" % count)
            Servers.add_nodes(count)
            # artificially delay the decision in order to discard transient measurements
            sleep(env_vars['extra_decision_delay_per_node']*count)
        elif action == "REMOVE":
            decision_module.pending_action = action
            my_logger.info("Will remove %d nodes" % count)
            Servers.remove_nodes(count)
            #not supposed to be here for pass decsion

        #update the hosts files in clients
        Clients.update_hostfiles(Servers.get_hosts())
        # update the state
        decision_module.pending_action = None
        decision_module.currentState = Servers.node_count()
    except Exception as e:
        #in case the action was failed set a globall error var as true
        global error
        error = e

running_process = None


def check_for_error():
    global error
    if not (error is None):
        my_logger.error("I detected an error in a previous action. Raising exception")
        my_logger.error("Message:" + str(error))
        running_process.terminate()
        raise error


def run(timeout=None):
    """
    Runs cluster with automatic decision taking
    @param timeout: the time in seconds this run should last
    """
    my_logger.debug("run: Time starts now, the experiment will take %d sec" % (timeout))
    # convert relative timeout to absolute time
    if not timeout is None: timeout = time() + timeout
    my_logger.debug("run: start time: %d - end time: %d" % (time(), timeout))

    #set global error to None
    global error
    error = None

    #init the decision module
    global decision_module
    decision_module = DM(monitoring_endpoint, Servers.node_count())

    #the time interval between metrics refresh
    metrics_interval = env_vars["metric_fetch_interval"]

    # main loop that fetches metric and takes decisions
    while (timeout is None) or (time() <= timeout):

        check_for_error()

        sleep(metrics_interval)
        # refresh the metrics
        all_metrics = monVms.refreshMetrics()

        #take a decision based on the new metrics
        global decision
        decision = decision_module.take_decision(all_metrics)

        # asynchronously implement that decision
        if(decision["action"]=="PASS"):
            continue
        global running_process
        if not running_process is None:
            running_process.join()
        running_process = Thread(target=implement_decision, args=())
        running_process.start()

    # DONE
    #join the running_process
    running_process.join()
    my_logger.info(" run is finished")


def train():
    """
    Runs a training phase in order to collect a training set of metrics for the given cluster
    """
    #change the gain function for training purposes
    env_vars['gain'] = 'num_nodes'

    # load the training vars into the regular enviroment vars
    t_vars = env_vars["training_vars"]
    env_vars['decision_interval'] = t_vars['decision_interval']
    env_vars['period'] = t_vars['period']
    env_vars['max_cluster_size'] = t_vars['max_cluster_size']
    env_vars['min_cluster_size'] = t_vars['min_cluster_size']
    env_vars["add_nodes"] = 1
    env_vars["rem_nodes"] = 1
    env_vars["measurements_file"] = env_vars["training_file"]
    env_vars['decision_threshold'] = 0
    # remove the old measurements/training file so that it is replaced
    try:remove(env_vars["measurements_file"])
    except: pass

    # Sanity-Check the nodecount
    if Servers.node_count() != t_vars['min_cluster_size']:
        my_logger.error("TRAINING: Start training with the Minimum cluster size, %d (now:%d)" %(t_vars['min_cluster_size'], Servers.node_count()))
        exit()

    # get the workload parameters
    svr_hosts = Servers.get_hosts(private=True)
    #create the parameters dictionary for the training phase
    params = {'type': 'sinusoid', 'servers': svr_hosts, 'target': t_vars['target_load'],
              'offset': t_vars['offset_load'], 'period': t_vars['period']}

    # init the decision module
    global decision_module
    decision_module = DM(monitoring_endpoint, Servers.node_count())
    #the time interval between metrics refresh
    metrics_interval = env_vars["metric_fetch_interval"]

    # run 1 period of workload for each of the the states between min and max cluster size
    for i in range(env_vars['max_cluster_size'] - t_vars['min_cluster_size'] + 1):
        print "iteration "+str(i)

        #run the workload with the specified params to the clients
        Clients.run(params)

        #refresh once
        all_metrics = monVms.refreshMetrics()
        #This should only decide to add a node after a period is passed
        global decision
        decision = decision_module.take_decision(all_metrics)

        #run for 1 period
        timeout = time() + env_vars['period']
        while time() <= timeout:
        #fetch metrics and takes decisions
            sleep(metrics_interval)
            # refresh the metrics
            all_metrics = monVms.refreshMetrics()

            #This should only decide to add a node after a period is passed
            decision = decision_module.take_decision(all_metrics)

            # synchronously implement that decision
            implement_decision()


        #stop the clients after one period has passed
        Clients.kill_nodes()

    my_logger.info("TRAINING DONE")


def test_vars():
    print env_vars['gain']
    print env_vars['max_cluster_size']