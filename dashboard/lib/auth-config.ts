/**
 * Cognito 인증 설정
 *
 * 환경 변수에서 Cognito User Pool ID, App Client ID, Region을 읽어
 * Amplify Auth 설정을 구성한다.
 */

import { Amplify } from "aws-amplify";

const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? "";
const userPoolClientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";
const region = process.env.NEXT_PUBLIC_COGNITO_REGION ?? "us-east-1";

export const authConfig = {
  Auth: {
    Cognito: {
      userPoolId,
      userPoolClientId,
      loginWith: {
        email: true,
      },
    },
  },
};

export function configureAmplify() {
  Amplify.configure(authConfig);
}

export { userPoolId, userPoolClientId, region };
