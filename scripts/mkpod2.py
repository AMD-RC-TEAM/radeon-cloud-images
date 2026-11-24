import json, sys
# name image node command [hfcache]
name, image, node, cmd = sys.argv[1:5]; hf = len(sys.argv) > 5
mounts = [{"name": "bench", "mountPath": "/bench"}, {"name": "shm", "mountPath": "/dev/shm"}]
vols = [{"name": "bench", "configMap": {"name": "rc-images-perf2"}}, {"name": "shm", "emptyDir": {"medium": "Memory", "sizeLimit": "16Gi"}}]
if hf:
    mounts.append({"name": "hf", "mountPath": "/hf-cache", "readOnly": True})
    vols.append({"name": "hf", "hostPath": {"path": "/nvme0/data/rc-images-ci-hf-cache", "type": "Directory"}})
spec = {"restartPolicy": "Never", "activeDeadlineSeconds": 5400, "terminationGracePeriodSeconds": 5, "automountServiceAccountToken": False,
        "nodeName": node,
        "containers": [{"name": "bench", "image": image, "imagePullPolicy": "IfNotPresent",
                        "command": ["bash", "-c", "ulimit -c 0; export HSA_DISABLE_COREDUMP_ON_EXCEPTION=1 HOME=/tmp; cd /tmp; " + cmd],
                        "resources": {"requests": {"cpu": "8", "memory": "48Gi", "amd.com/gpu": "1"},
                                      "limits": {"cpu": "8", "memory": "48Gi", "amd.com/gpu": "1"}},
                        "volumeMounts": mounts}], "volumes": vols}
print(json.dumps({"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name, "namespace": "test",
      "labels": {"app": "rc-images-perf2", "owner": "rc-images"}}, "spec": spec}))
