import logging
from typing import Dict, Text, Any, List
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher, Action
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import AllSlotsReset, SlotSet
from actions.snow import SnowAPI
import random
from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from .database import connect_to_db, create_tables,  \
     add_feedback, add_feedback_tables, get_user_incident, add_or_update_user_incidents

logger = logging.getLogger(__name__)
vers = "vers: 0.1.0, date: Apr 2, 2020"
logger.debug(vers)

snow = SnowAPI()
localmode = snow.localmode
logger.debug(f"Local mode: {snow.localmode}")


class ActionAskEmail(Action):
    def name(self) -> Text:
        return "action_ask_email"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict]:
        if tracker.get_slot("previous_email"):
            dispatcher.utter_message(template=f"utter_ask_use_previous_email", )
        else:
            dispatcher.utter_message(template=f"utter_ask_email")
        return []


def _validate_email(
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
) -> Dict[Text, Any]:
    """Validate email is in ticket system."""
    if not value:
        return {"email": None, "previous_email": None}
    elif isinstance(value, bool):
        value = tracker.get_slot("previous_email")

    if localmode:
        return {"email": value}

    results = snow.email_to_sysid(value)
    caller_id = results.get("caller_id")

    if caller_id:
        return {"email": value, "caller_id": caller_id}
    elif isinstance(caller_id, list):
        dispatcher.utter_message(template="utter_no_email")
        return {"email": None}
    else:
        dispatcher.utter_message(results.get("error"))
        return {"email": None}


class ValidateOpenIncidentForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_open_incident_form"

    def validate_email(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate email is in ticket system."""
        return _validate_email(value, dispatcher, tracker, domain)

    def validate_priority(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate priority is a valid value."""

        if value.lower() in snow.priority_db():
            return {"priority": value}
        else:
            dispatcher.utter_message(template="utter_no_priority")
            return {"priority": None}


class ActionOpenIncident(Action):
    def name(self) -> Text:
        return "action_open_incident"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Create an incident and return details or
        if localmode return incident details as if incident
        was created
        """
        conn = connect_to_db("users.db")
        create_tables(conn)
        priority = tracker.get_slot("priority")
        email = tracker.get_slot("email")
        problem_description = tracker.get_slot("problem_description")
        incident_title = tracker.get_slot("incident_title")
        confirm = tracker.get_slot("confirm")
        if not confirm:
            dispatcher.utter_message(
                template="utter_incident_creation_canceled"
            )
            return [AllSlotsReset(), SlotSet("previous_email", email)]

        if localmode:
            message = (
                f"An incident with the following details would be opened "
                f"if ServiceNow was connected:\n"
                f"email: {email}\n"
                f"problem description: {problem_description}\n"
                f"title: {incident_title}\npriority: {priority}"
            )
        else:
            snow_priority = snow.priority_db().get(priority)
            response = snow.create_incident(
                description=problem_description,
                short_description=incident_title,
                priority=snow_priority,
                email=email,
            )
            incident_number = (
                response.get("content", {}).get("result", {}).get("number")
            )
            if incident_number:
                message = (
                    f"Successfully opened up incident {incident_number} "
                    f"for you. Someone will reach out soon."
                )
            else:
                message = (
                    f"Something went wrong while opening an incident for you. "
                    f"{response.get('error')}"
                )
        dispatcher.utter_message(message)

        add_or_update_user_incidents(conn, str(email), str(priority), str(incident_title), str(problem_description))
        conn.close()
        return [AllSlotsReset(), SlotSet("previous_email", email)]


class IncidentStatusForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_incident_status_form"

    def validate_email(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate email is in ticket system."""
        return _validate_email(value, dispatcher, tracker, domain)


class ActionCheckIncidentStatus(Action):
    def name(self) -> Text:
        return "action_check_incident_status"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Look up all incidents associated with email address
           and return status of each"""

        email = tracker.get_slot("email")

        incident_states = {
            "New": "is currently awaiting triage",
            "In Progress": "is currently in progress",
            "On Hold": "has been put on hold",
            "Closed": "has been closed",
        }
        if localmode:
            status = random.choice(list(incident_states.values()))
            message = (
                f"Since ServiceNow isn't connected, I'm making this up!\n"
                f"The most recent incident for {email} {status}"
            )
        else:
            incidents_result = snow.retrieve_incidents(email)
            incidents = incidents_result.get("incidents")
            if incidents:
                message = "\n".join(
                    [
                        f'Incident {i.get("number")}: '
                        f'"{i.get("short_description")}", '
                        f'opened on {i.get("opened_at")} '
                        f'{incident_states.get(i.get("incident_state"))}'
                        for i in incidents
                    ]
                )

            else:
                message = f"{incidents_result.get('error')}"

        dispatcher.utter_message(message)
        return [AllSlotsReset(), SlotSet("previous_email", email)]


class ActionCreateNewUserAccident(Action):
    def name(self):
        return "action_create_new_user_accident"

    def run(self, dispatcher, tracker, domain):
        # Подключение к базе данных и создание таблицы, если она еще не существует
        conn = connect_to_db("users.db")
        create_tables(conn)

        # Приветствие пользователя.
        dispatcher.utter_message(template=f"utter_user_no_profile_created")
        # Пользователь создаёт аккаунт.
        # add
        # add_or_update_user_accident(conn, accident_id, user_id, accident_status, accident_text)
        # Пользователь создал аккаунт.
        dispatcher.utter_message(template=f"utter_show_user_email")
        dispatcher.utter_message(template=f"utter_user_profile_created")

        conn.close()

        return [SlotSet("user_accident_updated", True)]


class ActionCreateNewFeedback(Action):
    def name(self):
        return "action_create_new_feedback"

    def run(
            self,
            dispatcher: "CollectingDispatcher",
            tracker: Tracker,
            domain: "DomainDict",
    ) -> List[Dict[Text, Any]]:
        """Создаёт сообщение, которое записывается в базу данных."""

        conn = connect_to_db("users.db")
        add_feedback_tables(conn)
        message = tracker.get_slot("feedback_message")
        # message = "Привет. Это тестовый отзыв. Он достаточно длинный чтобы никто не увидел что автор этого сообщения наговнокодил хуйни и пытается её запустить."
        add_feedback(conn, message)
        dispatcher.utter_message(template=f"utter_feedback_accepted")
        return [AllSlotsReset()]

class ActionGetAllUserIncidents(Action):
    def name(self):
        return "action_get_all_user_incidents"

    def run(
            self,
            dispatcher: "CollectingDispatcher",
            tracker: Tracker,
            domain: "DomainDict",
    ) -> List[Dict[Text, Any]]:
        """Создаёт сообщение, которое выводит список инцидетов юзера по его эмейлу."""
        user_email = tracker.get_slot("user_email")
        conn = connect_to_db("users.db")
        create_tables(conn)
        message = get_user_incident(conn, user_email)
        dispatcher.utter_message(message)
        return [AllSlotsReset()]