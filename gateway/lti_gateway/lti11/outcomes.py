import logging
import uuid
import xml.etree.ElementTree as ET

import requests

from .oauth1 import sign_outcome_request

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
CONTENT_TYPE = "application/xml"

_REPLACE_RESULT = """<?xml version="1.0" encoding="UTF-8"?>
<imsx_POXEnvelopeRequest xmlns="http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0">
  <imsx_POXHeader>
    <imsx_POXRequestHeaderInfo>
      <imsx_version>V1.0</imsx_version>
      <imsx_messageIdentifier>{message_id}</imsx_messageIdentifier>
    </imsx_POXRequestHeaderInfo>
  </imsx_POXHeader>
  <imsx_POXBody>
    <replaceResultRequest>
      <resultRecord>
        <sourcedGUID>
          <sourcedId>{sourced_id}</sourcedId>
        </sourcedGUID>
        <result>
          <resultScore>
            <language>en</language>
            <textString>{score}</textString>
          </resultScore>
        </result>
      </resultRecord>
    </replaceResultRequest>
  </imsx_POXBody>
</imsx_POXEnvelopeRequest>"""


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _code_major(xml_text: str) -> str | None:
    """imsx_codeMajor value from a POX response, ignoring the namespace
    (implementations vary in which XSD version/namespace they declare)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "imsx_codeMajor":
            return (element.text or "").strip().lower()
    return None


def send_replace_result(outcome_service_url, consumer_key, consumer_secret, sourced_id, score) -> bool:
    """Submits a normalized 0.0-1.0 score via LTI 1.1 Basic Outcomes
    (replaceResult). Returns True only on a provider-reported `success`;
    never raises.
    """
    body = _REPLACE_RESULT.format(
        message_id=uuid.uuid4().hex, sourced_id=_escape(sourced_id), score=f"{score:.4f}"
    )
    uri, headers, signed_body = sign_outcome_request(
        outcome_service_url, consumer_key, consumer_secret, body, CONTENT_TYPE
    )
    try:
        response = requests.post(
            uri, data=signed_body, headers={**headers, "Content-Type": CONTENT_TYPE}, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException:
        log.warning("Basic Outcomes request failed", exc_info=True)
        return False

    success = _code_major(response.text) == "success"
    if not success:
        log.warning("Basic Outcomes provider reported failure: %s", response.text[:500])
    return success
