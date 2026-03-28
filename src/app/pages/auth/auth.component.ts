import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Auth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signInWithPopup, GoogleAuthProvider } from '@angular/fire/auth';
import { Firestore, doc, setDoc } from '@angular/fire/firestore';
import { MessageService } from 'primeng/api';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.scss'
})
export class AuthComponent implements OnInit {
  isLoginMode = true;
  isLoading = false;
  authForm!: FormGroup;

  private auth: Auth = inject(Auth);
  private firestore: Firestore = inject(Firestore);
  private messageService: MessageService = inject(MessageService);
  private router: Router = inject(Router);

  constructor(private fb: FormBuilder) {}

  ngOnInit() {
    this.initForm();
  }

  initForm() {
    if (this.isLoginMode) {
      this.authForm = this.fb.group({
        email: ['', [Validators.required, Validators.email]],
        password: ['', [Validators.required, Validators.minLength(6)]],
        rememberMe: [false]
      });
    } else {
      this.authForm = this.fb.group({
        username: ['', Validators.required],
        email: ['', [Validators.required, Validators.email]],
        password: ['', [Validators.required, Validators.minLength(6)]]
      });
    }
  }

  toggleMode() {
    this.isLoginMode = !this.isLoginMode;
    this.initForm();
  }

  onSubmit() {
    if (this.authForm.invalid) {
      this.authForm.markAllAsTouched();
      return;
    }

    this.isLoading = true;
    const { email, password, username } = this.authForm.value;

    if (this.isLoginMode) {
      signInWithEmailAndPassword(this.auth, email, password).then(() => {
        this.isLoading = false;
        this.messageService.add({ severity: 'success', summary: 'Welcome Back!', detail: 'Successfully logged in.' });
        this.handleSuccessfulAuth(this.authForm.value.rememberMe);
      }).catch(err => {
        this.isLoading = false;
        this.messageService.add({ severity: 'error', summary: 'Login Failed', detail: err.message });
      });
    } else {
      createUserWithEmailAndPassword(this.auth, email, password).then((resp) => {
        const userRef = doc(this.firestore, `users/${resp.user.uid}`);
        setDoc(userRef, {
          username: username,
          email: email,
          createdAt: new Date().toISOString()
        });
        
        this.isLoading = false;
        this.messageService.add({ severity: 'success', summary: 'Account Created', detail: 'You have signed up successfully!' });
        this.handleSuccessfulAuth(false);
      }).catch(err => {
        this.isLoading = false;
        this.messageService.add({ severity: 'error', summary: 'Sign Up Failed', detail: err.message });
      });
    }
  }
  
  signInWithGoogle() {
    this.isLoading = true;
    const provider = new GoogleAuthProvider();

    signInWithPopup(this.auth, provider).then(() => {
      this.isLoading = false;
      this.messageService.add({ severity: 'success', summary: 'Welcome!', detail: 'Google Sign-In successful.' });
      this.handleSuccessfulAuth(this.isLoginMode ? this.authForm.value.rememberMe : false);
    }).catch(err => {
      this.isLoading = false;
      this.messageService.add({ severity: 'error', summary: 'Google Sign-In Failed', detail: err.message });
    });
  }

  private handleSuccessfulAuth(rememberMe: boolean) {
    if (!rememberMe) {
      localStorage.setItem('sessionExpiry', (Date.now() + 60 * 60 * 1000).toString());
    } else {
      localStorage.removeItem('sessionExpiry');
    }
    
    this.router.navigate(['/dashboard']);
  }
}
