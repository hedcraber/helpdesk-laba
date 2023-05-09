from rasa_sdk import Action
from rasa_sdk.events import SlotSet

class ActionCreateOrUpdateUserProfile(Action):
    def name(self):
        return "action_create_or_update_user_profile"

    def run(self, dispatcher, tracker, domain):
        user_id = tracker.sender_id
        user_name = tracker.get_slot("user name")
        user_email = tracker.get_slot("user_email")

        dispatcher.utter_message(text=f"Личный кабинет пользователя {user_name}")
        return [SlotSet("user_profile_updated", True)]
