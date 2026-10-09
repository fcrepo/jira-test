debugging readme.txt for Fedora 2.2 maintenance patch 6012 (2007.06.18)


DEBUGGING SUPPORT -- VERSION CONFIGURATION

Additional configuration options are now available at patch level 6012
All are optional.

One of these is simple to describe and use, and may be required in a 
non-problem installation.

version
ldap protocol version that jndi/ldap client should use to connect to ldap server
value is one of: 2, 3 (default: 2)



DEBUG SUPPORT -- LOGGING

To turn on debug-level logging for servlet filter and related code,
edit your installation's server/config/log4j.properties file.
Insert the following new line
log4j.logger.fedora.server.security=DEBUG, FEDORA
after the existing line
log4j.logger.fedora=INFO, FEDORA

Restart Fedora to put this debug logging into play.



DEBUG SUPPORT -- ADDITIONAL CONFIGURATION OPTIONS


the following is necessarily complicated, and intended only to 
deal with unexpected behavior from an underlying directory call.  
You only need to read further if you are having a problem in using 
the ldap servlet filter.  Otherwise, this may be unnecessarily 
tedious and likely confusing.

First see the general readme.txt for this patch.  readme.txt is 
available from sourceforge under either of the related issues:  
https://sourceforge.net/tracker/index.php?func=detail&aid=1721620&group_id=177054&atid=879703
https://sourceforge.net/tracker/index.php?func=detail&aid=1731608&group_id=177054&atid=879703
and is included in distribution file fedora-2.2.6012.zip at those
same locations.

Configuration options are documented at the fedora.info website or 
after running the "ant docs" target locally.  These are unchanged by
the fixes documented in these readme.txt files.
See userdocs/server/security/securingrepo.html 

Additional configuration options are also available to work around JNDI/LDAP 
problems seen in the field, but not in core development/testing.  You should 
not use these options unless you are debugging a related problem.  They 
apply only to the ldap servlet filter.

    
null-password
-------------
how should a null-valued password be handled?
value is one of: use-filter, unauthenticate-user-unconditionally, skip-filter 
default: use-filter

so the ldap filter can 
either let ldap handle the null password (null-password==use-filter) 
or impose unauthentication, without calling ldap (null-password==unauthenticate-user-unconditionally)
or get out of the way (null-password==skip-filter)

details on init-parm "null-password":

if the http password is null, 

condition 1:  if null-password==use-filter
operation:  pass it normally to jndi/ldap for continued processing
 
condition 2:  if null-password==skip-filter
operation:  skip this servlet filter 
(it neither contributes to authentication decision nor returns attributes/groups)

condition 3:  if null-password==unauthenticate-user-unconditionally
operation:  fail the processing as if the underlying directory call did throw a naming exception

condition 2 and 3 are applied only if AUTHENTICATE is configured true;
otherwise, the servlet filter is used normally

    
zerolength-password
-------------------
how should a non-null, but zero-length ("") password be handled?
value is one of: use-filter, unauthenticate-user-unconditionally, skip-filter
default: use-filter

so the ldap filter can 
either let ldap handle the zero-length ("") password (zerolength-password==use-filter) 
or impose unauthentication, without calling ldap (zerolength-password==unauthenticate-user-unconditionally)
or get out of the way (zerolength-password==skip-filter)

operation for zerolength-password is similar to null-password.


empty-results
-------------
how should well-formed but empty results from a directory search be interpreted?
value is one of: 
unauthenticate-user-conditionally, 
use-filter, unauthenticate-user-unconditionally, skip-filter
default: unauthenticate-user-conditionally

so the ldap filter can 
either let ldap handle the empty results (empty-results==use-filter) 
or impose unauthentication, after calling ldap (empty-results==unauthenticate-user-unconditionally)
or impose unauthentication, after calling ldap, but only if attributes were expected back from directory
(empty-results==unauthenticate-user-conditionally)
or get out of the way (empty-results==skip-filter)

details on init-parm "empty-results":

if the results from a directory search are well-formed but empty, and no underlying exception was thrown 

first see if this applies:
condition:  system (non-user) bind was configured
operation:  fail the processing as if the underlying directory call did throw a naming exception, 
regardless of how empty-results is configured

second apply these:
condition:  if empty-results==use-filter
operation:  pass it normally to jndi/ldap for continued processing
 
condition:  if empty-results==skip-filter
operation:  skip this servlet filter
(it neither contributes to authentication decision nor returns attributes/groups)

condition:  if empty-results==unauthenticate-user-unconditionally
operation:  fail the processing as if the underlying directory call did throw a naming exception

condition:  if empty-results==unauthenticate-user-conditionally
	a. and attributes were configured to be returned 
	(i.e., init-parm "attributes" was configured with a comma-separated list of n>0 values)
operation:  fail the processing as if the underlying directory call did throw a naming exception
	b. and no attributes were configured to be returned 
	(i.e., init-parm "attributes" was not configured with a comma-separated list of n>0 values)
operation:  accept this as ok (this would allow for legitimate empty results in authenticate-only use)

all conditions are applied only if init-parm "authenticate" is configured true and a user directory bind is 
required for this;
otherwise, the servlet filter is used normally



DEBUG SUPPORT -- ADDITIONAL CONFIGURATION OPTIONS (I)

If a null- or zerolength- ("") user password is wrongly authenticated by your ldap servlet filter,
first check the configuration.  If you believe that it's appropriate, try the following
trouble-shooting:


1. Make sure that you haven't added the additional option "empty-results" to your web.xml ldap 
servlet filter configuration.  Or, if you have done so, that it has the default value as follows:

<init-param>
  <param-name>empty-results</param-name> 
  <param-value>unauthenticate-user-conditionally</param-value> 
</init-param>


2. You probably have values configured for the init-parm "attributes" in the Fedora webapp's
web.xml, in its ldap servlet filter configuration.  But if you don't -- and you might not 
if using ldap only for authentication and not also for attributes/groups -- configure for 
an attribute to be returned, even if it's not ever used in an xacml policy.  

Here's an example:

<init-param>
  <param-name>attributes</param-name> 
  <param-value>ou</param-value> 
</init-param>


Restart Fedora with any changes you made for 1 or 2 directly above.  If you are still having problems, 
you have two alternate paths:


DEBUG SUPPORT -- ADDITIONAL CONFIGURATION OPTIONS (II-A)


You can now collect some logging info to help understand the problem.  To do this, you should set 
debug logging on (see the top of this debugging-readme.txt) and do a limited test where you see
the problem.  Then stop Fedora.  The log file at server/logs/fedora.log should contain mostly startup 
messages, but also those showing the problem.  Rename the log file so that it's not added to or 
overwritten.  Report the problem to fedora-users.


DEBUG SUPPORT -- ADDITIONAL CONFIGURATION OPTIONS (II-B)


3. Or you can configure the ldap servlet filter to itself handle what may be a problem with 
the underlying connection to ldap.  To do this, add the following additional options to 
web.xml, in its ldap servlet filter configuration:

<init-param>
  <param-name>null-password</param-name> 
  <param-value>unauthenticate-user-unconditionally</param-value> 
</init-param>
<init-param>
  <param-name>zerolength-password</param-name> 
  <param-value>unauthenticate-user-unconditionally</param-value> 
</init-param>


 	  	 
