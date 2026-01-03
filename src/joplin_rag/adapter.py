from allauth.account.adapter import DefaultAccountAdapter

class MyAccountAdapter(DefaultAccountAdapter):
    def get_user_display_name(self, user):
        """
        Use email as the display name in messages.
        """
        return user.email
