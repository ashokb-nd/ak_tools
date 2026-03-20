import json


def read_events(summary_file, event_type="events_data"):
    import json
    with open(summary_file, 'r') as f:
        summary_data = json.load(f)
    return summary_data.get("inference_data", {}).get(event_type, {}).get("alerts", [])

def read_event_codes(summary_file):
    events = read_events(summary_file)
    return [event.get("event_code") for event in events]

def read_alerts(summary_file):
    return read_events(summary_file, event_type="alerts_data")

def read_alert_codes(summary_file):
    alerts = read_alerts(summary_file)
    return [alert.get("event_code") for alert in alerts]

def pick_an_alert(summary_file, event_code):
    alerts = read_alerts(summary_file)
    data = [alert for alert in alerts if alert.get("event_code")== event_code]
    return data

def pick_an_event(summary_file,event_code):
    events = read_events(summary_file)
    data = [event for event in events if event.get("event_code")== event_code]
    return data
    
def get_starttime(summary_file):
    with open(summary_file, 'r') as f:
        summary_data = json.load(f)
    return summary_data.get("startTime", None)

def extract_PIL(summary_file):
    with open(summary_file, "r") as f:
        summary_data = json.load(f)
    PIL = summary_data.get("inference_data",{}).get("observations_data",{}).get("positionsInLane",[])
    return PIL

def extract_yaw(summary_file):
    with open(summary_file, 'r') as f:
        summary_content = json.load(f)

    sensor_data = summary_content['sensorMetaData']
    yaw_values = []
    for entry in sensor_data:
        if 'gyro' in entry:
            gyro_data = entry['gyro']
            yaw, pitch, roll, ts = gyro_data.split()
            yaw_values.append((int(ts), float(yaw)))
    return yaw_values

def extract_acceleration(summary_file):
    with open(summary_file, 'r') as f:
        summary_content = json.load(f)

    sensor_data = summary_content['sensorMetaData']
    acc_values = []
    for entry in sensor_data:
        if 'accelerometer' in entry:
            acc_data = entry['accelerometer']
            acc_z, acc_lateral, acc_driving, ts = acc_data.split()
            acc_values.append((int(ts), float(acc_lateral), float(acc_driving), float(acc_z)))
    return acc_values

def extract_acc_lateral(summary_file):
    acc_values = extract_acceleration(summary_file)
    return [(ts, acc_lat) for ts, acc_lat, _, _ in acc_values]

def ld_summary_only_alerts(summary_file):
    with open(summary_file, 'r') as f:
        summary_content = json.load(f)
    alerts = summary_content.get("inference_data", {}).get("dms", {}).get("dms_drowsy",{}).get("drowsy_p2", {}).get("ld_combo_summary_only", [])
    return alerts

def extract_ld(summary_file):
    with open(summary_file, 'r') as f:
        data = json.load(f)
    extd_eh =  data.get('inference_data', {}).get('observations_data', {}).get('drowsy_sensor_fusion_events_extended_event_history', {})
    if not isinstance(extd_eh, dict):
        return None
    ld_history = extd_eh.get('lane_deviation_history', None)
    return ld_history