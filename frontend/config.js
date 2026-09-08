// Public runtime config for the `dev` stack. None of these are secrets —
// a Cognito App Client ID, User Pool ID, and API base URL are meant to be
// embedded in a browser app. Values come from `a72-recon0-dev`'s stack
// outputs (see DEPLOY.md). When `prod` gets wired into the pipeline, this
// needs a per-stage variant instead of one static file.
window.A72_CONFIG = {
  region: "eu-south-2",
  userPoolId: "eu-south-2_1kVFInPji",
  userPoolClientId: "11eo51bssrr3ugct3bnndmctks",
  apiUrl: "https://vqlgkuzm72.execute-api.eu-south-2.amazonaws.com/dev",
};
