## 环境变量
### `K8S_IP`
可选的。指定Kubernetes master IP。默认是127.0.0.1。

### `HEAT_IP`
可选的。指定heat的IP。默认是127.0.0.1。

### `ETCD_PORT`
可选的。指定ETCD的端口号。默认是4001。

### `HEAT_USERNAME`
必须的。连接heat时的用户名。

### `HEAT_PASSWORD`
必须的。连接heat时的密码

### `HEAT_AUTH_URL`
必须的。连接heat时，认证url。例如HEAT_AUTH_URL=http://127.0.0.1:35357/v2.0

### `MAX_LOG_SIZE`
可选的。paas-api的当前日志文件大小，单位是MB。默认是20。

### `MAX_LOG_COUNT`
可选的。日志滚动时，最大文件个数。默认是10。

### `PORT`
可选的。paas-api运行时所绑定的端口。默认是12306

### `DEBUG`
可选的。是否开启debug模式。默认是True。

### `USE_THREAD`
可选的。是否开启多线程模式。默认是True。

### `BINDING_ADDR`
可选的。paas-api运行时所绑定的IP地址。默认是0.0.0.0

### `USE_RELOADER`
可选的。是否开启reloader。默认是True。

### `ACL`
可选的。paas-api的访问控制策略。默认是任意client可以访问任意的资源。

