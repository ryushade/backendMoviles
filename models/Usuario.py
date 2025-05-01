class Usuario(object):
    def __init__(self, id, email_user, pass_user):
        self.id = id
        self.email_user = email_user
        self.pass_user = pass_user

    def __str__(self):
        return "User(id='%s')" % self.id
    
    def json(self):
        return {
            "id": self.id,
            "email_user": self.email_user,
            "pass_user": self.pass_user
        }