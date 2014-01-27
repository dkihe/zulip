from __future__ import absolute_import

from django.views.decorators.csrf import csrf_exempt
from zerver.models import get_client

from zerver.decorator import asynchronous, \
    authenticated_json_post_view, internal_notify_view, RespondAsynchronously, \
    has_request_variables, REQ

from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_bool, check_list, check_string
from zerver.lib.event_queue import allocate_client_descriptor, get_client_descriptor, \
    process_notification, fetch_events
from zerver.lib.narrow import check_supported_events_narrow_filter

import ujson
import logging

from zerver.lib.rest import rest_dispatch as _rest_dispatch
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))

@internal_notify_view
def notify(request):
    process_notification(ujson.loads(request.POST['data']))
    return json_success()

@has_request_variables
def cleanup_event_queue(request, user_profile, queue_id=REQ()):
    client = get_client_descriptor(queue_id)
    if client is None:
        return json_error("Bad event queue id: %s" % (queue_id,))
    if user_profile.id != client.user_profile_id:
        return json_error("You are not authorized to access this queue")
    request._log_data['extra'] = "[%s]" % (queue_id,)
    client.cleanup()
    return json_success()

@authenticated_json_post_view
def json_get_events(request, user_profile):
    return get_events_backend(request, user_profile, apply_markdown=True)

@asynchronous
@has_request_variables
def get_events_backend(request, user_profile, handler = None,
                       user_client = REQ(converter=get_client, default=None),
                       last_event_id = REQ(converter=int, default=None),
                       queue_id = REQ(default=None),
                       apply_markdown = REQ(default=False, validator=check_bool),
                       all_public_streams = REQ(default=False, validator=check_bool),
                       event_types = REQ(default=None, validator=check_list(check_string)),
                       dont_block = REQ(default=False, validator=check_bool),
                       narrow = REQ(default=[], validator=check_list(None)),
                       lifespan_secs = REQ(default=0, converter=int)):
    if user_client is None:
        user_client = request.client

    (result, log_data) = fetch_events(
        user_profile.id, user_profile.realm_id, user_profile.email, queue_id,
        last_event_id, event_types, user_client, apply_markdown, all_public_streams,
        lifespan_secs, narrow, dont_block, handler)
    request._log_data['extra'] = log_data
    if result == RespondAsynchronously:
        handler._request = request
    return result
