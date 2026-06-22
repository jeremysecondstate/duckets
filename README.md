## Duckets Law

Every file, class, function, method, constant, setting, dependency, and UI element must have a reason to exist today.

Code is only allowed if it is directly used by the current app.

No placeholder modules.
No speculative abstractions.
No unused helpers.
No copied legacy code unless it has been rewritten and connected.
No “we might need this later.”
No feature survives without a visible purpose.

Before committing, every new symbol must answer:

1. What uses this today?
2. What breaks if this is deleted?
3. Is this simpler than the alternative?

If the answer is unclear, delete it.