'use client';

import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { ReactNode, useEffect } from 'react';
import { configureAmplify } from '../lib/auth-config';

export default function AuthProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    configureAmplify();
  }, []);

  return (
    <Authenticator>
      {({ signOut, user }) => (
        <div data-user-email={user?.signInDetails?.loginId ?? ''}>
          {children}
        </div>
      )}
    </Authenticator>
  );
}
