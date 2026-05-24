TOPIC

Create (simple):
kafka-topics.sh --bootstrap-server localhost:9092 --create --topic whatsapp_notification

Create (detailed):
kafka-topics.sh --bootstrap-server localhost:9092 --create --topic whatsapp_notification --partitions 4 --replication-factor 2

List:
kafka-topics.sh --bootstrap-server localhost:9092 --list

Describe:
kafka-topics.sh --bootstrap-server localhost:9092 --describe

Delete:
kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic whatsapp_notification


PRODUCER

kafka-console-producer.sh --topic whatsapp_notification --bootstrap-server localhost:9092

Producer with key/value
kafka-console-producer.sh \
  --topic whatsapp_notification \
  --bootstrap-server localhost:9092 \
  --property parse.key=true \
  --property key.separator=:

Usage
When it starts, you can type messages like:
user1:Hello WhatsApp
user2:Payment reminder
user3:Order delivered


CONSUMER

kafka-console-consumer.sh --topic whatsapp_notification --from-beginning --bootstrap-server localhost:9092      👉 Consumes all messages from the beginning of the topic. If you omit --from-beginning, the consumer will start consuming from the latest offset, only receiving new messages published after it starts. 

With properties (print key, value, partition, offset):
kafka-console-consumer.sh \
  --topic whatsapp_notification \
  --bootstrap-server localhost:9092 \
  --group whatsapp_consumer_grp \              👉 To make it resume from where it stopped, you need to use a consumer group so that offsets are committed and stored in Kafka.
  --property print.key=true \
  --property print.value=true \
  --property print.partition=true \
  --property print.offset=true


EXAMPLE:

Here is the Kafka cluster representation for 2 brokers, 2 partitions, replication factor 2:
Kafka Cluster: 2 Brokers, 2 Partitions, Replication Factor 2
+------------------+------------------+
|    Broker 1      |    Broker 2      |
|                  |                  |
| P0 (Leader)      | P1 (Leader)      |
| P1 (Replica)     | P0 (Replica)     |
+------------------+------------------+


+------------------------------------------+
|           Kafka Message (Record)         |
+------------------------------------------+
| Topic: "orders"                          |
| Partition: (Decided by Key or Round-robin)|
| Key: "order-12345" (Ensures Ordering per Key)|
| Value: {                                 |
|   "order_id": "12345",                   |
|   "customer": "John Doe",                |
|   "amount": 250.75,                      |
|   "status": "pending"                    |
| }                                        |
| Headers: { "source": "web-app", "timestamp": "1700000000000" } |
| Timestamp: "1700000000000"               |
+------------------------------------------+


What it Zookeeper?

ZooKeeper is a distributed coordination service that manages
synchronization, configuration, and leader election in
distributed systems.

It basically ensures everything stays in sync and knows what's
happening where.


What it Kraft?

Kraft (Kafka Raft) is Kafka's new way of handling coordination
and metadata without needing ZooKeeper.

It uses a built-in Raft consensus protocol so that Kafka
brokers manage everything themselves.
