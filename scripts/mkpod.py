import json, sys
name, image, node = sys.argv[1:4]
spec = {"restartPolicy": "Never", "activeDeadlineSeconds": 3600, "terminationGracePeriodSeconds": 5, "automountServiceAccountToken": False,
        "nodeName": node,
        "containers": [{"name": "bench", "image": image, "imagePullPolicy": "IfNotPresent",
                        "command": ["bash", "/bench/run.sh"],
                        "resources": {"requests": {"cpu": "8", "memory": "32Gi", "amd.com/gpu": "1"},
                                      "limits": {"cpu": "8", "memory": "32Gi", "amd.com/gpu": "1"}},
                        "volumeMounts": [{"name": "bench", "mountPath": "/bench"}, {"name": "shm", "mountPath": "/dev/shm"}]}],
        "volumes": [{"name": "bench", "configMap": {"name": "rc-images-base-perf"}},
                    {"name": "shm", "emptyDir": {"medium": "Memory", "sizeLimit": "8Gi"}}]}
print(json.dumps({"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name, "namespace": "test",
      "labels": {"app": "rc-images-base-perf", "owner": "rc-images"}}, "spec": spec}))
