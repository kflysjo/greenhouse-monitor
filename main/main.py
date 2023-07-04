import time                   # Allows use of time.sleep() for delays
from mqtt import MQTTClient   # For use of MQTT protocol to talk to Adafruit IO
import ubinascii              # Conversions between binary data and various encodings
import machine                # Interfaces with hardware components
import micropython            # Needed to run any MicroPython code
from machine import Pin       # Define pin
import dht
import json
import utime
 
 



# BEGIN SETTINGS
# System settings
MQTT_SEND_INTERVAL = 20000    # milliseconds
TEMP_LIMIT_HIGH = 40
TEMP_LIMIT_LOW = 5
FULL_FIFO_LEN = 10
temp_pred_one_h = 0
last_random_sent_ticks = 0  # milliseconds
FIFO_temp = []
temp_der = 0
temp_high_flag = False
temp_low_flag = False
soil_moisture_percentage = 50

# MQTT configurations
MQTT_SERVER = "192.168.0.179"
MQTT_PORT = 1883
MQTT_USER = "this"
MQTT_KEY = "time"
MQTT_CLIENT_ID = ubinascii.hexlify(machine.unique_id())  # Can be anything
MQTT_DHT_FEED = "devices/greenhouse"

# Pin configuration
tempSensor = dht.DHT22(machine.Pin(18))   # DHT22 Constructor for pin GPIO18
soil_moisture_port = machine.ADC(26)

# END SETTINGS


# FUNCTIONS

# Function to read sensors and send values to MQTT server at fixed interval
def send_readings():
    global last_random_sent_ticks
    global MQTT_SEND_INTERVAL
    global temp_pred_one_h
    global temp_high_flag
    global temp_low_flag
    global soil_moisture_percentage

    if ((time.ticks_ms() - last_random_sent_ticks) < MQTT_SEND_INTERVAL):
        return; # Too soon since last one sent.


    # Reading the DHT22
    try: 
        tempSensor.measure()
        temperature = tempSensor.temperature()
        humidity = tempSensor.humidity()
        print("Temperature is {} degrees Celsius and Humidity is {}%".format(temperature, humidity))
    except Exception as error:
        print("Exception occurred", error)
    time.sleep(2)

    FIFO_temp.append(temperature)


    if (len(FIFO_temp) > FULL_FIFO_LEN-1):
        FIFO_temp.pop(0)

    if (FIFO_temp[0] < FIFO_temp[-1]):
        temp_pred_one_h = temperature + (max(FIFO_temp) - min(FIFO_temp)) / len(FIFO_temp) * 60
    else:
        temp_pred_one_h = temperature - (max(FIFO_temp) - min(FIFO_temp)) / len(FIFO_temp) * 60

    
    if (temp_pred_one_h > TEMP_LIMIT_HIGH):
        temp_high_flag = 1
    else: 
        temp_high_flag = 0

    if (temp_pred_one_h < TEMP_LIMIT_LOW):
        temp_low_flag = 1
    else: 
        temp_low_flag = 0

    #print("temp prediction: " + str(temp_pred_one_h))

    # Reading the ADC
    soil_moisture_reading = soil_moisture_port.read_u16()
    soil_moisture_percentage = (45000/260)-(soil_moisture_reading/260)  


    send_buffer = {
   "temp" : temperature,
   "humid" : humidity,
   "high_temp" : temp_high_flag,
   "low_temp" : temp_low_flag,
   "soil_moisture" : soil_moisture_percentage
   }
    
    json_send_buffer = json.dumps(send_buffer)

    # Publishing the sensor readings
    print("Publishing: {0} to {1} ... ".format(json_send_buffer, MQTT_DHT_FEED), end='')
    try:
        client.publish(topic=MQTT_DHT_FEED, msg=str(json_send_buffer))
        print("DONE")
    except Exception as e:
        print("FAILED")
    finally:
        last_random_sent_ticks = time.ticks_ms()



# Use the MQTT protocol to connect to Adafruit IO
client = MQTTClient(MQTT_CLIENT_ID, MQTT_SERVER, MQTT_PORT, MQTT_USER, MQTT_KEY)

# Subscribed messages will be delivered to this callback
client.connect()


try:                      # Code between try: and finally: may cause an error
                          # so ensure the client disconnects the server if
                          # that happens.
    while 1:              # Repeat this loop forever
        client.check_msg()# Action a message if one is received. Non-blocking.
        send_readings()     # Send a random number to Adafruit IO if it's time.
finally:                  # If an exception is thrown ...
    client.disconnect()   # ... disconnect the client and clean up.
    client = None
    print("Disconnected from MQTT-broker.")