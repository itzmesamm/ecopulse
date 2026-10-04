EC2_STOP_ACTION_CODE = "aws.ec2.stop"
EC2_STOP_ACTION_LABEL = "stop idle ec2 instance"


def resolve_live_action_code(action: str | None) -> str | None:
    if (action or "").strip().lower() == EC2_STOP_ACTION_LABEL:
        return EC2_STOP_ACTION_CODE
    return None