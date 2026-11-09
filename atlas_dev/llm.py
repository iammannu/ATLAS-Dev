"""GMI Cloud Router integration for ATLAS Dev."""

import json
import os
import urllib.error
import urllib.request


def ask_ai(prompt):
    api_key = os.getenv("GMI_API_KEY")
    if not api_key:
        raise RuntimeError("GMI_API_KEY is missing")

    url = os.getenv(
        "GMI_ROUTER_URL",
        "https://console.gmicloud.ai/api/v1/ie/recommendation/autoroute",
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are ATLAS Dev, a Python coding assistant. "
                    "Provide accurate, testable programming guidance."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "mode": "balanced",
        "stream": False,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"GMI Router returned HTTP {exc.code}"
        ) from exc

    if "message" in result:
        return result["message"]["content"]

    choices = result.get("choices", [])
    if choices:
        return choices[0]["message"]["content"]

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    print(ask_ai(
        "Explain Python's AST module in two sentences."
    ))
