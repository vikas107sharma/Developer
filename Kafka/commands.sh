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

kafka-console-consumer.sh --topic whatsapp_notification --from-beginning --bootstrap-server localhost:9092

With properties (print key, value, partition, offset):
kafka-console-consumer.sh --topic whatsapp_notification \
  --from-beginning \
  --bootstrap-server localhost:9092 \
  --property print.key=true \
  --property print.value=true \
  --property print.partition=true \
  --property print.offset=true