
The following text was pulled from README.md, and needs to be re-written and
possibly re-inserted somewhere in the project...

## Developer Perspective:

The acceptable library helps developers provide a predictable API to clients.
It does this by requiring developers to annotate views with two pieces of
information:

 1. The version number the view was introduced at.
 2. The API Flag (if any) that the view is present under.


### Version Numbers

A version number follows a simple 'X.Y' pattern: 'X' is the *major* version
number, and 'Y' is the *minor* version number. Both the major and minor version
numbers can be any integer >= 0. Major version numbers indicate backwards
-incompatible changes to the API. Obviously creating a backwards-incompatible
change is something that should be avoided at all costs, so major version
numbers should be rarely updated. Minor version numbers indicate backwards
compatible changes, and should be updated any time some new functionality
is introduced to the API.

Clients specify the preferred version number they support. If a client supports
API version '1.3', any '1.x' version less than, or equal to '1.3' may be
used to satisfy the client's request.

### API Flags


API Flags allow developers to expose experimental APIs to clients that
understand that opting in to use those experimental APIs carries significant
risk. As a general rule, clients in production should never use views behind
API flags.

Once these experimental features have reached maturity, the API flag is removed
from the view(s) in question, and the views are introduced at a newer API
version number.

## TODO:

 - can we somehow encode what view was selected in the response? Could use
   content-type, but that will wreak havock with requests ets, so let's not do
   that.
