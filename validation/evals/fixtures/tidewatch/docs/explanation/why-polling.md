# Why tidewatch polls

Kernel notifications such as inotify are fast, but they do not cross network
mounts and some container file systems. Polling costs a little CPU and some
delay, and behaves the same everywhere. The poll interval sets the trade-off.
