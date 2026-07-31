ACCESS_KEY=""
SECRET_KEY=""
REGION=""

MQTT_ENDPOINT = ""
MQTT_TOPIC=""

# Topic the data_to_rds Lambda confirms stored records on. {device} is replaced
# with device<DEVICE_ID>. Must be identical to ACK_TOPIC_TEMPLATE in that
# Lambda's config.py, or generated stations never confirm anything.
# Format: "<your-ack-prefix>/{device}"
ACK_TOPIC_TEMPLATE = ""