import re

from django import forms

import commonware.log
import happyforms
from tower import ugettext_lazy as _lazy

import amo
from users.forms import BaseAdminUserEditForm
from users.models import UserProfile

log = commonware.log.getLogger('z.users')
admin_re = re.compile('(?=.*\d)(?=.*[a-zA-Z])')


class UserEditForm(happyforms.ModelForm):
    display_name = forms.CharField(label=_lazy(u'Display Name'), max_length=50,
        required=True,
        help_text=_lazy(u'This will be publicly displayed next to your '
                         'ratings, collections, and other contributions.'))
    lang = forms.CharField(required=False)
    region = forms.CharField(required=False)

    class Meta:
        model = UserProfile
        fields = 'display_name', 'lang', 'region'


class AdminUserEditForm(BaseAdminUserEditForm, UserEditForm):
    """
    This extends from the old `AdminUserEditForm` but using our new fancy
    `UserEditForm`.
    """
    admin_log = forms.CharField(required=True, label='Reason for change',
                                widget=forms.Textarea(attrs={'rows': 4}))
    notes = forms.CharField(required=False, label='Notes',
                            widget=forms.Textarea(attrs={'rows': 4}))
    anonymize = forms.BooleanField(required=False)
    restricted = forms.BooleanField(required=False)

    def save(self, *args, **kw):
        profile = super(AdminUserEditForm, self).save()
        if self.cleaned_data['anonymize']:
            amo.log(amo.LOG.ADMIN_USER_ANONYMIZED, self.instance,
                    self.cleaned_data['admin_log'])
            profile.anonymize()  # This also logs.
        else:
            if ('restricted' in self.changed_data and
                self.cleaned_data['restricted']):
                amo.log(amo.LOG.ADMIN_USER_RESTRICTED, self.instance,
                        self.cleaned_data['admin_log'])
                profile.restrict()
            else:
                amo.log(amo.LOG.ADMIN_USER_EDITED, self.instance,
                        self.cleaned_data['admin_log'], details=self.changes())
                log.info('Admin edit user: %s changed fields: %s' %
                         (self.instance, self.changed_fields()))
        return profile


class UserDeleteForm(forms.Form):
    confirm = forms.BooleanField(
        label=_lazy(u'I understand this step cannot be undone.'))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UserDeleteForm, self).__init__(*args, **kwargs)

    def clean(self):
        amouser = self.request.user.get_profile()
        if amouser.is_developer:
            # This is tampering because the form isn't shown on the page if
            # the user is a developer.
            log.warning(u'[Tampering] Attempt to delete developer account (%s)'
                                                          % self.request.user)
            raise forms.ValidationError('Developers cannot delete their '
                                        'accounts.')


class LoginForm(happyforms.Form):
    assertion = forms.CharField(required=True)
    audience = forms.CharField(required=False)
    is_native = forms.BooleanField(required=False)
