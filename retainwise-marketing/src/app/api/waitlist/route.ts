import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    console.log('API: Waitlist submission received');
    
    const { email } = await req.json();
    
    if (!email || !email.includes('@')) {
      console.log('API: Invalid email format');
      return NextResponse.json({ error: 'Invalid email' }, { status: 400 });
    }
    
    console.log('API: Valid email received:', email);
    
    // TODO: Add logic to save email or send notification
    // For now, just return success
    console.log('API: Email processed successfully');
    
    return NextResponse.json({ 
      success: true, 
      message: 'Successfully added to waitlist' 
    });
  } catch (e) {
    console.error('API: Server error:', e);
    return NextResponse.json({ error: 'Server error' }, { status: 500 });
  }
} 