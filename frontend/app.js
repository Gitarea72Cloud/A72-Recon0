// Shared auth + API helpers. Loaded after config.js and the
// amazon-cognito-identity-js CDN script on every page.
(function () {
  const CONFIG = window.A72_CONFIG;
  const userPool = new AmazonCognitoIdentity.CognitoUserPool({
    UserPoolId: CONFIG.userPoolId,
    ClientId: CONFIG.userPoolClientId,
  });

  function getCurrentUser() {
    return userPool.getCurrentUser();
  }

  // Resolves a valid (auto-refreshed if needed) ID token, or rejects if
  // nobody is signed in / the refresh token has expired.
  function getIdToken() {
    return new Promise((resolve, reject) => {
      const cognitoUser = getCurrentUser();
      if (!cognitoUser) return reject(new Error("not signed in"));
      cognitoUser.getSession((err, session) => {
        if (err) return reject(err);
        if (!session || !session.isValid()) return reject(new Error("session invalid"));
        resolve(session.getIdToken().getJwtToken());
      });
    });
  }

  function isSignedIn() {
    return getIdToken().then(() => true).catch(() => false);
  }

  // Client-side check only, for UI gating (show/hide the admin link) --
  // the real enforcement is server-side (auth.is_instructor on every
  // /admin/* route), this just avoids flashing admin UI at students.
  async function isInstructor() {
    try {
      const cognitoUser = getCurrentUser();
      if (!cognitoUser) return false;
      return await new Promise((resolve) => {
        cognitoUser.getSession((err, session) => {
          if (err || !session || !session.isValid()) return resolve(false);
          const groups = session.getIdToken().payload["cognito:groups"] || [];
          resolve(groups.indexOf("instructors") !== -1);
        });
      });
    } catch (e) {
      return false;
    }
  }

  function signOut() {
    const cognitoUser = getCurrentUser();
    if (cognitoUser) cognitoUser.signOut();
  }

  // username/password -> {status: "ok"} | {status: "newPasswordRequired", cognitoUser, userAttributes}
  function signIn(username, password) {
    return new Promise((resolve, reject) => {
      const authDetails = new AmazonCognitoIdentity.AuthenticationDetails({
        Username: username,
        Password: password,
      });
      const cognitoUser = new AmazonCognitoIdentity.CognitoUser({ Username: username, Pool: userPool });
      cognitoUser.authenticateUser(authDetails, {
        onSuccess: () => resolve({ status: "ok" }),
        onFailure: (err) => reject(err),
        newPasswordRequired: (userAttributes) => {
          delete userAttributes.email_verified;
          delete userAttributes.email;
          resolve({ status: "newPasswordRequired", cognitoUser, userAttributes });
        },
      });
    });
  }

  function completeNewPassword(cognitoUser, userAttributes, newPassword) {
    return new Promise((resolve, reject) => {
      cognitoUser.completeNewPasswordChallenge(newPassword, userAttributes, {
        onSuccess: () => resolve(),
        onFailure: (err) => reject(err),
      });
    });
  }

  async function apiFetch(path, options = {}) {
    const token = await getIdToken();
    const res = await fetch(CONFIG.apiUrl + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
        ...(options.headers || {}),
      },
    });
    let body = null;
    try { body = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) {
      const err = new Error((body && body.error) || res.statusText);
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  function redirectToSignIn(next) {
    const n = next || (location.pathname.split("/").pop() || "index.html");
    location.href = "signin.html?next=" + encodeURIComponent(n);
  }

  // Renders the auth-aware right side of the top nav into el.
  async function renderAuthNav(el) {
    const signedIn = await isSignedIn();
    if (signedIn) {
      const user = getCurrentUser();
      const instructor = await isInstructor();
      el.innerHTML =
        (instructor ? '<a href="admin.html">Admin</a>' : "") +
        '<span class="muted" style="font-size:13px">' + (user ? user.getUsername() : "") + "</span>" +
        '<a href="#" id="signOutLink">Sign out</a>';
      document.getElementById("signOutLink").addEventListener("click", (e) => {
        e.preventDefault();
        signOut();
        location.href = "index.html";
      });
    } else {
      el.innerHTML = '<a href="signin.html">Sign in</a>';
    }
    return signedIn;
  }

  window.A72 = {
    userPool, getCurrentUser, getIdToken, isSignedIn, isInstructor, signOut,
    signIn, completeNewPassword, apiFetch, redirectToSignIn, renderAuthNav,
  };
})();
