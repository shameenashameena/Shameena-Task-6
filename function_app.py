import logging
from datetime import datetime, timezone
import azure.functions as func

# Initialize Function App
app = func.FunctionApp()


@app.function_name(name="timer_example")
@app.timer_trigger(
    schedule="0 0 2 * * *",  # daily at 02:00 UTC
    arg_name="mytimer",
    run_on_startup=True
)
def timer_example(mytimer: func.TimerRequest) -> None:
    # Current UTC timestamp
    utc_timestamp = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    # Check if timer is past due
    if mytimer.past_due:
        logging.warning("The timer is past due!")

    # Log the execution
    logging.info("Python timer trigger function ran at %s", utc_timestamp)
